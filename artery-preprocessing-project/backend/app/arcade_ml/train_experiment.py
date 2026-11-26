"""Reproducible CPU/GPU training for non-destructive ARCADE experiments.

The original checkpoint is never overwritten. Validation selects checkpoints.
The train dataset loader reads validation hashes only to exclude exact
duplicates. It does not access the test split.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, WeightedRandomSampler

from app.arcade_ml.dataset import ArcadeSegDataset
from app.arcade_ml.losses import BCEDiceLoss
from app.arcade_ml.models import build_model, count_parameters
from app.arcade_ml.paths import checkpoints_dir, complete_project_root


def seed_everything(seed: int) -> None:
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(seed)
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


def _metric_counts(logits: torch.Tensor, masks: torch.Tensor) -> tuple[list[dict], tuple[int, int, int, int]]:
    pred = torch.sigmoid(logits) >= 0.5
    truth = masks >= 0.5
    axes = (1, 2, 3)
    tp = (pred & truth).sum(axes).cpu().numpy()
    fp = (pred & ~truth).sum(axes).cpu().numpy()
    fn = (~pred & truth).sum(axes).cpu().numpy()
    tn = (~pred & ~truth).sum(axes).cpu().numpy()
    per_image = []
    for a, b, c, d in zip(tp, fp, fn, tn):
        a, b, c, d = int(a), int(b), int(c), int(d)
        eps = 1e-7
        per_image.append({"dice": (2*a+eps)/(2*a+b+c+eps), "iou": (a+eps)/(a+b+c+eps),
                          "precision": (a+eps)/(a+b+eps), "recall": (a+eps)/(a+c+eps),
                          "specificity": (d+eps)/(d+b+eps)})
    return per_image, (int(tp.sum()), int(fp.sum()), int(fn.sum()), int(tn.sum()))


def _finish_metrics(per_image: list[dict], counts: tuple[int, int, int, int]) -> dict:
    tp, fp, fn, tn = counts
    eps = 1e-7
    precision = (tp+eps)/(tp+fp+eps); recall=(tp+eps)/(tp+fn+eps)
    return {
        "macro_dice": float(np.mean([m["dice"] for m in per_image])) if per_image else 0.0,
        "macro_iou": float(np.mean([m["iou"] for m in per_image])) if per_image else 0.0,
        "macro_precision": float(np.mean([m["precision"] for m in per_image])) if per_image else 0.0,
        "macro_recall_sensitivity": float(np.mean([m["recall"] for m in per_image])) if per_image else 0.0,
        "macro_specificity": float(np.mean([m["specificity"] for m in per_image])) if per_image else 0.0,
        "global_tp": tp, "global_fp": fp, "global_fn": fn, "global_tn": tn,
        "global_dice": float((2*tp+eps)/(2*tp+fp+fn+eps)),
        "global_iou": float((tp+eps)/(tp+fp+fn+eps)),
        "global_precision": float(precision), "global_recall_sensitivity": float(recall),
        "global_f1": float((2*precision*recall)/(precision+recall+eps)),
        "global_specificity": float((tn+eps)/(tn+fp+eps)),
    }


def train_epoch(model, loader, optimizer, loss_fn, device, scaler, grad_accumulation: int = 1, use_amp: bool = False) -> dict:
    model.train(); losses=[]; images_seen=0; per_image=[]; totals=np.zeros(4,dtype=np.int64)
    optimizer.zero_grad(set_to_none=True)
    for batch_index, (images, masks, _names) in enumerate(loader):
        images, masks = images.to(device), masks.to(device)
        with torch.autocast(device_type=device.type, enabled=use_amp):
            logits = model(images)
        loss = loss_fn(logits.float(), masks.float())
        group_start = (batch_index // grad_accumulation) * grad_accumulation
        group_size = min(grad_accumulation, len(loader) - group_start)
        scaler.scale(loss / group_size).backward()
        should_step = (batch_index + 1) % grad_accumulation == 0 or batch_index + 1 == len(loader)
        if should_step:
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            scaler.step(optimizer); scaler.update(); optimizer.zero_grad(set_to_none=True)
        losses.append(float(loss.detach().item())); images_seen += images.shape[0]
        batch_metrics, batch_counts = _metric_counts(logits.detach(), masks)
        per_image.extend(batch_metrics); totals += np.asarray(batch_counts)
    return {"loss": float(np.average(losses)) if losses else 0.0, "samples": images_seen,
            **_finish_metrics(per_image, tuple(int(x) for x in totals))}


@torch.inference_mode()
def evaluate(model, loader, loss_fn, device, use_amp: bool = False) -> dict:
    model.eval(); losses=[]; per_image=[]; totals=np.zeros(4,dtype=np.int64); seen=0
    for images, masks, _names in loader:
        images, masks = images.to(device), masks.to(device)
        with torch.autocast(device_type=device.type, enabled=use_amp):
            logits = model(images)
        loss = loss_fn(logits.float(),masks.float())
        losses.append(float(loss.item())); seen += images.shape[0]
        batch_metrics, batch_counts = _metric_counts(logits, masks)
        per_image.extend(batch_metrics); totals += np.asarray(batch_counts)
    return {"loss": float(np.average(losses)) if losses else 0.0, "samples": seen,
            **_finish_metrics(per_image, tuple(int(x) for x in totals))}


def _save_graphs(history: list[dict], directory: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    epochs = [row["epoch"] for row in history]
    for metric, filename, ylabel in (("loss", "loss_curve.png", "Loss"),
                                     ("macro_dice", "dice_curve.png", "Macro Dice"),
                                     ("macro_iou", "iou_curve.png", "Macro IoU")):
        fig, ax = plt.subplots(figsize=(8, 5))
        for split in ("train", "val"):
            ax.plot(epochs, [row[split][metric] for row in history], marker="o", label=split)
        ax.set(xlabel="Epoch", ylabel=ylabel); ax.grid(True, alpha=0.25); ax.legend()
        fig.tight_layout(); fig.savefig(directory / filename, dpi=150); plt.close(fig)


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=("stenosis", "syntax"), default="stenosis",
                        help="Train the lesion task or union of SYNTAX-annotated coronary artery segments.")
    parser.add_argument("--epochs",type=int,default=8); parser.add_argument("--batch-size",type=int,default=4)
    parser.add_argument("--image-size",type=int,default=256); parser.add_argument("--base-channels",type=int,default=16)
    parser.add_argument("--learning-rate",type=float,default=0.0005); parser.add_argument("--pos-weight",type=float,default=5.0)
    parser.add_argument("--architecture",choices=("resunet","unet","attention_unet","smp_unet","smp_unetplusplus","smp_deeplabv3plus"),default="resunet")
    parser.add_argument("--encoder-name",default="resnet34")
    parser.add_argument("--encoder-weights",choices=("imagenet","none"),default="none")
    parser.add_argument("--normalization",choices=("none","imagenet"),default="none")
    parser.add_argument("--loss",choices=("bce_dice","tversky","focal","focal_tversky"),default="bce_dice")
    parser.add_argument("--optimizer",choices=("adamw","adam"),default="adamw")
    parser.add_argument("--scheduler",choices=("plateau","cosine"),default="plateau")
    parser.add_argument("--augmentation",choices=("conservative","legacy"),default="conservative")
    parser.add_argument("--positive-sample-weight",type=float,default=1.0)
    parser.add_argument("--grad-accumulation",type=int,default=1)
    parser.add_argument("--amp",action="store_true")
    parser.add_argument("--patience",type=int,default=4); parser.add_argument("--seed",type=int,default=20261124)
    parser.add_argument("--threads",type=int,default=min(8,torch.get_num_threads()))
    parser.add_argument("--output",type=Path,default=None)
    args=parser.parse_args()
    if args.output is None:
        if args.task == "stenosis" and args.architecture == "resunet":
            args.output = checkpoints_dir() / "resunet16_stenosis_experiment.pth"
        else:
            args.output = checkpoints_dir() / f"{args.architecture}_{args.task}_experiment.pth"
    if args.grad_accumulation < 1:
        parser.error("--grad-accumulation must be at least 1")
    if args.positive_sample_weight < 1.0:
        parser.error("--positive-sample-weight must be at least 1.0")
    seed_everything(args.seed); torch.set_num_threads(max(1,args.threads))
    device=torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_set=ArcadeSegDataset(args.task,"train",image_size=args.image_size,augment=True,
                               augmentation_mode=args.augmentation,normalization=args.normalization)
    val_set=ArcadeSegDataset(args.task,"val",image_size=args.image_size,augment=False,
                             normalization=args.normalization)
    generator=torch.Generator().manual_seed(args.seed)
    train_weights=[]
    for record in train_set.records:
        if args.task == "stenosis":
            has_target=any(int(annotation.get("category_id",-1))==26 and annotation.get("segmentation")
                           for annotation in record["annotations"])
        else:
            has_target=any(annotation.get("segmentation") for annotation in record["annotations"])
        train_weights.append(args.positive_sample_weight if has_target else 1.0)
    sampler=WeightedRandomSampler(train_weights,num_samples=len(train_weights),replacement=True) if args.positive_sample_weight>1 else None
    train_loader=DataLoader(train_set,batch_size=args.batch_size,shuffle=sampler is None,sampler=sampler,num_workers=0,
                            pin_memory=device.type=="cuda",generator=generator)
    val_loader=DataLoader(val_set,batch_size=args.batch_size,shuffle=False,num_workers=0,
                          pin_memory=device.type=="cuda")
    pretrained_weights = args.encoder_weights if args.encoder_weights != "none" else None
    model=build_model(args.architecture,base=args.base_channels,
                      encoder_name=args.encoder_name if args.architecture.startswith("smp_") else None,
                      encoder_weights=pretrained_weights if args.architecture.startswith("smp_") else None).to(device)
    smp_version=None
    if args.architecture.startswith("smp_"):
        import segmentation_models_pytorch as smp
        smp_version=smp.__version__
    if args.loss == "tversky":
        from app.arcade_ml.losses import TverskyLoss
        loss_fn=TverskyLoss(alpha=0.7,beta=0.3)
    elif args.loss == "focal":
        from app.arcade_ml.losses import BinaryFocalLoss
        loss_fn=BinaryFocalLoss(gamma=2.0,pos_weight=args.pos_weight)
    elif args.loss == "focal_tversky":
        from app.arcade_ml.losses import FocalTverskyLoss
        loss_fn=FocalTverskyLoss(alpha=0.7,beta=0.3,gamma=0.75)
    else:
        loss_fn=BCEDiceLoss(pos_weight=args.pos_weight)
    optimizer_cls=torch.optim.AdamW if args.optimizer == "adamw" else torch.optim.Adam
    optimizer=optimizer_cls(model.parameters(),lr=args.learning_rate,weight_decay=1e-4 if args.optimizer == "adamw" else 0.0)
    scheduler=(torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=max(1,args.epochs))
               if args.scheduler=="cosine" else
               torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer,mode="max",factor=0.5,patience=2))
    use_amp=bool(args.amp and device.type=="cuda")
    scaler=torch.cuda.amp.GradScaler(enabled=use_amp)
    output=args.output if not args.output.exists() else next(args.output.with_name(f"{args.output.stem}_run{i:02d}{args.output.suffix}") for i in range(1,1000) if not args.output.with_name(f"{args.output.stem}_run{i:02d}{args.output.suffix}").exists())
    output.parent.mkdir(parents=True,exist_ok=True)
    experiment_dir=complete_project_root()/"reports"/"model_validation"/output.stem
    experiment_dir.mkdir(parents=True,exist_ok=True)
    history=[]; best=-1.; best_epoch=0; stale=0; started=time.perf_counter()
    print(f"device={device} train={len(train_set)} val={len(val_set)} excluded_cross_split_duplicates={train_set.excluded_duplicates} excluded_within_split_duplicates={train_set.excluded_within_split_duplicates} params={count_parameters(model)}")
    for epoch in range(1,args.epochs+1):
        train_stats=train_epoch(model,train_loader,optimizer,loss_fn,device,scaler,
                                max(1,args.grad_accumulation),use_amp)
        val_stats=evaluate(model,val_loader,loss_fn,device,use_amp)
        if args.scheduler=="cosine": scheduler.step()
        else: scheduler.step(val_stats["macro_dice"])
        row={"epoch":epoch,"lr":optimizer.param_groups[0]["lr"],"train":train_stats,"val":val_stats}
        history.append(row); print(json.dumps(row))
        if val_stats["macro_dice"]>best:
            best=val_stats["macro_dice"]; best_epoch=epoch; stale=0
            torch.save({"model_name":args.architecture,"architecture":args.architecture,"task":args.task,
                "image_size":args.image_size,"base_channels":args.base_channels,"in_channels":3,"out_channels":1,
                "target_semantics":"union of annotated SYNTAX coronary artery segment polygons; not stenosis or validated lumen-caliber labels" if args.task == "syntax" else "category-26 stenosis lesion polygons",
                "normalization":args.normalization,
                "threshold":0.5,"best_val_dice":best,"val_iou":val_stats["macro_iou"],"epoch":epoch,
                "seed":args.seed,"loss":args.loss,"optimizer":args.optimizer,"learning_rate":args.learning_rate,
                "encoder_name":args.encoder_name if args.architecture.startswith("smp_") else None,
                "encoder_weights":pretrained_weights if args.architecture.startswith("smp_") else None,
                "smp_version":smp_version,
                "batch_size":args.batch_size,"epochs_requested":args.epochs,"pos_weight":args.pos_weight,
                "scheduler":args.scheduler,"augmentation":args.augmentation,
                "positive_sample_weight":args.positive_sample_weight,"gradient_accumulation":args.grad_accumulation,
                "mixed_precision":use_amp,
                "excluded_cross_split_duplicates":train_set.excluded_duplicates,
                "excluded_within_split_duplicates":train_set.excluded_within_split_duplicates,
                "train_metrics":train_stats,"validation_metrics":val_stats,"history":history,
                "parameters":count_parameters(model),"state_dict":model.state_dict()},output)
        else:
            stale+=1
            if stale>=args.patience: break
    elapsed=time.perf_counter()-started
    checkpoint_data=torch.load(output,map_location="cpu",weights_only=False)
    checkpoint_data["best_epoch"]=best_epoch
    checkpoint_data["training_time_seconds"]=elapsed
    checkpoint_data["hardware"]={"device":str(device),"torch_version":torch.__version__,
                                  "cuda_available":torch.cuda.is_available(),"threads":torch.get_num_threads()}
    torch.save(checkpoint_data,output)
    config={"experiment_id":output.stem,"task":args.task,
        "target_semantics":"union of annotated SYNTAX coronary artery segment polygons; not stenosis or validated lumen-caliber labels" if args.task == "syntax" else "category-26 stenosis lesion polygons",
        "architecture":args.architecture,
        "encoder":args.encoder_name if args.architecture.startswith("smp_") else "none (trained from scratch)",
        "encoder_weights":pretrained_weights if args.architecture.startswith("smp_") else None,
        "smp_version":smp_version,
        "input_size":args.image_size,"loss":args.loss,"optimizer":args.optimizer,"learning_rate":args.learning_rate,
        "normalization":args.normalization,
        "batch_size":args.batch_size,"epochs_requested":args.epochs,"best_epoch":best_epoch,"seed":args.seed,
        "positive_weight":args.pos_weight,"augmentation":args.augmentation,
        "scheduler":args.scheduler,"positive_sample_weight":args.positive_sample_weight,
        "gradient_accumulation":args.grad_accumulation,"mixed_precision":use_amp,
        "training_time_seconds":elapsed,"hardware":checkpoint_data["hardware"],"checkpoint_path":str(output),
        "training_samples":len(train_set),"validation_samples":len(val_set),
        "excluded_cross_split_duplicates":train_set.excluded_duplicates,
        "excluded_within_train_duplicates":train_set.excluded_within_split_duplicates,
        "best_train_metrics":checkpoint_data.get("train_metrics"),
        "best_validation_metrics":checkpoint_data.get("validation_metrics")}
    (experiment_dir/"experiment_config.json").write_text(json.dumps(config,indent=2),encoding="utf-8")
    history_path=experiment_dir/"training_history.json"
    history_path.write_text(json.dumps(history,indent=2),encoding="utf-8")
    _save_graphs(history,experiment_dir)
    print(json.dumps({"checkpoint":str(output),"history":str(history_path),"graphs":str(experiment_dir),
        "best_epoch":best_epoch,"training_time_seconds":elapsed,"best_macro_val_dice":best},indent=2))


if __name__=="__main__": main()
