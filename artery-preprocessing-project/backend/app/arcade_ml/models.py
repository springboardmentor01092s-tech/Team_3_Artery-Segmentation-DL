from __future__ import annotations

import torch
import torch.nn as nn


class ConvBlock(nn.Module):
    def __init__(self, in_ch: int, out_ch: int):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)


class AttentionGate(nn.Module):
    def __init__(self, g_ch: int, x_ch: int, inter_ch: int):
        super().__init__()
        self.w_g = nn.Sequential(nn.Conv2d(g_ch, inter_ch, 1, bias=True), nn.BatchNorm2d(inter_ch))
        self.w_x = nn.Sequential(nn.Conv2d(x_ch, inter_ch, 1, bias=True), nn.BatchNorm2d(inter_ch))
        self.psi = nn.Sequential(nn.Conv2d(inter_ch, 1, 1, bias=True), nn.BatchNorm2d(1), nn.Sigmoid())
        self.relu = nn.ReLU(inplace=True)

    def forward(self, g: torch.Tensor, x: torch.Tensor) -> torch.Tensor:
        att = self.relu(self.w_g(g) + self.w_x(x))
        return x * self.psi(att)


class UNet(nn.Module):
    def __init__(self, in_channels: int = 3, out_channels: int = 1, base: int = 32):
        super().__init__()
        self.enc1 = ConvBlock(in_channels, base)
        self.enc2 = ConvBlock(base, base * 2)
        self.enc3 = ConvBlock(base * 2, base * 4)
        self.enc4 = ConvBlock(base * 4, base * 8)
        self.pool = nn.MaxPool2d(2)
        self.bottleneck = ConvBlock(base * 8, base * 16)
        self.up4 = nn.ConvTranspose2d(base * 16, base * 8, 2, stride=2)
        self.dec4 = ConvBlock(base * 16, base * 8)
        self.up3 = nn.ConvTranspose2d(base * 8, base * 4, 2, stride=2)
        self.dec3 = ConvBlock(base * 8, base * 4)
        self.up2 = nn.ConvTranspose2d(base * 4, base * 2, 2, stride=2)
        self.dec2 = ConvBlock(base * 4, base * 2)
        self.up1 = nn.ConvTranspose2d(base * 2, base, 2, stride=2)
        self.dec1 = ConvBlock(base * 2, base)
        self.head = nn.Conv2d(base, out_channels, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        e4 = self.enc4(self.pool(e3))
        b = self.bottleneck(self.pool(e4))
        d4 = self.dec4(torch.cat([self.up4(b), e4], dim=1))
        d3 = self.dec3(torch.cat([self.up3(d4), e3], dim=1))
        d2 = self.dec2(torch.cat([self.up2(d3), e2], dim=1))
        d1 = self.dec1(torch.cat([self.up1(d2), e1], dim=1))
        return self.head(d1)


class AttentionUNet(nn.Module):
    def __init__(self, in_channels: int = 3, out_channels: int = 1, base: int = 32):
        super().__init__()
        self.enc1 = ConvBlock(in_channels, base)
        self.enc2 = ConvBlock(base, base * 2)
        self.enc3 = ConvBlock(base * 2, base * 4)
        self.enc4 = ConvBlock(base * 4, base * 8)
        self.pool = nn.MaxPool2d(2)
        self.bottleneck = ConvBlock(base * 8, base * 16)
        self.up4 = nn.ConvTranspose2d(base * 16, base * 8, 2, stride=2)
        self.att4 = AttentionGate(base * 8, base * 8, base * 4)
        self.dec4 = ConvBlock(base * 16, base * 8)
        self.up3 = nn.ConvTranspose2d(base * 8, base * 4, 2, stride=2)
        self.att3 = AttentionGate(base * 4, base * 4, base * 2)
        self.dec3 = ConvBlock(base * 8, base * 4)
        self.up2 = nn.ConvTranspose2d(base * 4, base * 2, 2, stride=2)
        self.att2 = AttentionGate(base * 2, base * 2, base)
        self.dec2 = ConvBlock(base * 4, base * 2)
        self.up1 = nn.ConvTranspose2d(base * 2, base, 2, stride=2)
        self.att1 = AttentionGate(base, base, base // 2 if base >= 2 else 1)
        self.dec1 = ConvBlock(base * 2, base)
        self.head = nn.Conv2d(base, out_channels, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        e4 = self.enc4(self.pool(e3))
        b = self.bottleneck(self.pool(e4))
        g4 = self.up4(b)
        d4 = self.dec4(torch.cat([g4, self.att4(g4, e4)], dim=1))
        g3 = self.up3(d4)
        d3 = self.dec3(torch.cat([g3, self.att3(g3, e3)], dim=1))
        g2 = self.up2(d3)
        d2 = self.dec2(torch.cat([g2, self.att2(g2, e2)], dim=1))
        g1 = self.up1(d2)
        d1 = self.dec1(torch.cat([g1, self.att1(g1, e1)], dim=1))
        return self.head(d1)


class ResidualBlock(nn.Module):
    def __init__(self, in_ch: int, out_ch: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
        )
        self.skip = (
            nn.Identity()
            if in_ch == out_ch
            else nn.Sequential(nn.Conv2d(in_ch, out_ch, 1, bias=False), nn.BatchNorm2d(out_ch))
        )
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.relu(self.conv(x) + self.skip(x))


class ResidualUNet(nn.Module):
    """Residual U-Net used for Experiment 04B-style stenosis segmentation."""

    def __init__(self, in_channels: int = 3, out_channels: int = 1, base: int = 32):
        super().__init__()
        self.enc1 = ResidualBlock(in_channels, base)
        self.enc2 = ResidualBlock(base, base * 2)
        self.enc3 = ResidualBlock(base * 2, base * 4)
        self.enc4 = ResidualBlock(base * 4, base * 8)
        self.pool = nn.MaxPool2d(2)
        self.bottleneck = ResidualBlock(base * 8, base * 16)
        self.up4 = nn.ConvTranspose2d(base * 16, base * 8, 2, stride=2)
        self.dec4 = ResidualBlock(base * 16, base * 8)
        self.up3 = nn.ConvTranspose2d(base * 8, base * 4, 2, stride=2)
        self.dec3 = ResidualBlock(base * 8, base * 4)
        self.up2 = nn.ConvTranspose2d(base * 4, base * 2, 2, stride=2)
        self.dec2 = ResidualBlock(base * 4, base * 2)
        self.up1 = nn.ConvTranspose2d(base * 2, base, 2, stride=2)
        self.dec1 = ResidualBlock(base * 2, base)
        self.head = nn.Conv2d(base, out_channels, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        e4 = self.enc4(self.pool(e3))
        b = self.bottleneck(self.pool(e4))
        d4 = self.dec4(torch.cat([self.up4(b), e4], dim=1))
        d3 = self.dec3(torch.cat([self.up3(d4), e3], dim=1))
        d2 = self.dec2(torch.cat([self.up2(d3), e2], dim=1))
        d1 = self.dec1(torch.cat([self.up1(d2), e1], dim=1))
        return self.head(d1)


class DoubleConvNoBN(nn.Module):
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, 3, padding=1),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)


class LegacyAttentionGate(nn.Module):
    def __init__(self, skip_channels: int, gate_channels: int, inter_channels: int):
        super().__init__()
        self.skip_conv = nn.Sequential(
            nn.Conv2d(skip_channels, inter_channels, 1, bias=False),
            nn.BatchNorm2d(inter_channels),
        )
        self.gate_conv = nn.Sequential(
            nn.Conv2d(gate_channels, inter_channels, 1, bias=False),
            nn.BatchNorm2d(inter_channels),
        )
        self.attention = nn.Sequential(
            nn.ReLU(inplace=True),
            nn.Conv2d(inter_channels, 1, 1),
            nn.Sigmoid(),
        )

    def forward(self, skip: torch.Tensor, gate: torch.Tensor) -> torch.Tensor:
        combined = self.skip_conv(skip) + self.gate_conv(gate)
        return skip * self.attention(combined)


class LegacyUNet(nn.Module):
    """Matches baseline/stenosis_detection U-Net checkpoints (no BatchNorm, 3-level)."""

    def __init__(self, in_channels: int = 3, out_channels: int = 1):
        super().__init__()
        self.enc1 = DoubleConvNoBN(in_channels, 32)
        self.pool1 = nn.MaxPool2d(2)
        self.enc2 = DoubleConvNoBN(32, 64)
        self.pool2 = nn.MaxPool2d(2)
        self.enc3 = DoubleConvNoBN(64, 128)
        self.pool3 = nn.MaxPool2d(2)
        self.bottleneck = DoubleConvNoBN(128, 256)
        self.up3 = nn.ConvTranspose2d(256, 128, 2, stride=2)
        self.dec3 = DoubleConvNoBN(256, 128)
        self.up2 = nn.ConvTranspose2d(128, 64, 2, stride=2)
        self.dec2 = DoubleConvNoBN(128, 64)
        self.up1 = nn.ConvTranspose2d(64, 32, 2, stride=2)
        self.dec1 = DoubleConvNoBN(64, 32)
        self.output = nn.Conv2d(32, out_channels, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool1(e1))
        e3 = self.enc3(self.pool2(e2))
        b = self.bottleneck(self.pool3(e3))
        d3 = self.dec3(torch.cat([self.up3(b), e3], dim=1))
        d2 = self.dec2(torch.cat([self.up2(d3), e2], dim=1))
        d1 = self.dec1(torch.cat([self.up1(d2), e1], dim=1))
        return self.output(d1)


class LegacyAttentionUNet(nn.Module):
    """Matches baseline/attention_outputs_256 Attention U-Net checkpoints."""

    def __init__(self, in_channels: int = 3, out_channels: int = 1):
        super().__init__()
        self.enc1 = DoubleConvNoBN(in_channels, 32)
        self.pool1 = nn.MaxPool2d(2)
        self.enc2 = DoubleConvNoBN(32, 64)
        self.pool2 = nn.MaxPool2d(2)
        self.enc3 = DoubleConvNoBN(64, 128)
        self.pool3 = nn.MaxPool2d(2)
        self.bottleneck = DoubleConvNoBN(128, 256)
        self.up3 = nn.ConvTranspose2d(256, 128, 2, stride=2)
        self.att3 = LegacyAttentionGate(128, 128, 64)
        self.dec3 = DoubleConvNoBN(256, 128)
        self.up2 = nn.ConvTranspose2d(128, 64, 2, stride=2)
        self.att2 = LegacyAttentionGate(64, 64, 32)
        self.dec2 = DoubleConvNoBN(128, 64)
        self.up1 = nn.ConvTranspose2d(64, 32, 2, stride=2)
        self.att1 = LegacyAttentionGate(32, 32, 16)
        self.dec1 = DoubleConvNoBN(64, 32)
        self.output = nn.Conv2d(32, out_channels, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool1(e1))
        e3 = self.enc3(self.pool2(e2))
        b = self.bottleneck(self.pool3(e3))
        d3 = self.up3(b)
        d3 = self.dec3(torch.cat([d3, self.att3(e3, d3)], dim=1))
        d2 = self.up2(d3)
        d2 = self.dec2(torch.cat([d2, self.att2(e2, d2)], dim=1))
        d1 = self.up1(d2)
        d1 = self.dec1(torch.cat([d1, self.att1(e1, d1)], dim=1))
        return self.output(d1)


def detect_architecture(state_dict: dict, meta: dict | None = None) -> str:
    meta = meta or {}
    keys = list(state_dict.keys())
    if any(k.startswith("att3.skip_conv") for k in keys):
        return "legacy_attention_unet"
    if any(k.startswith("output.") for k in keys):
        return "legacy_unet"
    if any(k.startswith("att4.") for k in keys):
        return "attention_unet"
    if any(k.startswith("enc1.conv.") for k in keys) or any("skip.0.weight" in k for k in keys):
        return "resunet"
    name = str(meta.get("model_name") or meta.get("architecture") or "unet")
    return name.lower().replace("-", "_").replace(" ", "_")


def build_model(
    name: str,
    in_channels: int = 3,
    out_channels: int = 1,
    base: int = 32,
    encoder_name: str | None = None,
    encoder_weights: str | None = None,
) -> nn.Module:
    key = name.lower().replace("-", "_").replace(" ", "_")
    smp_architectures = {
        "smp_unet": "Unet",
        "smp_unetplusplus": "UnetPlusPlus",
        "smp_deeplabv3plus": "DeepLabV3Plus",
    }
    if key in smp_architectures:
        try:
            import segmentation_models_pytorch as smp
        except ImportError as exc:
            raise RuntimeError(
                "This checkpoint requires segmentation-models-pytorch. Install backend/requirements-ml.txt."
            ) from exc
        model_class = getattr(smp, smp_architectures[key])
        return model_class(
            encoder_name=encoder_name or "resnet34",
            encoder_weights=encoder_weights,
            in_channels=in_channels,
            classes=out_channels,
            activation=None,
        )
    if key in {"unet", "u_net"}:
        return UNet(in_channels, out_channels, base)
    if key in {"attention_unet", "attentionunet"}:
        return AttentionUNet(in_channels, out_channels, base)
    if key in {"resunet", "residual_unet", "res_unet"}:
        return ResidualUNet(in_channels, out_channels, base)
    if key in {"legacy_unet", "baseline_unet"}:
        return LegacyUNet(in_channels, out_channels)
    if key in {"legacy_attention_unet", "baseline_attention_unet"}:
        return LegacyAttentionUNet(in_channels, out_channels)
    raise ValueError(f"Unknown model '{name}'.")


def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)
