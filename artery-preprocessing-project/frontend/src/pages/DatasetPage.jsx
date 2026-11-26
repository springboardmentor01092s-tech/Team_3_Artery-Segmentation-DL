import { useEffect, useState } from "react";
import api from "../api/client";
import Notice from "../components/Notice";
import Spinner from "../components/Spinner";
import { apiError } from "../utils/errors";

function formatList(formats) {
  const entries = Object.entries(formats || {});
  if (!entries.length) return "None";
  return entries.map(([name, count]) => `${name}: ${count}`).join(", ");
}

function SourceCard({ title, source, emptyMessage }) {
  if (!source) return null;
  const empty = source.exists && source.supported_count === 0 && source.unreadable_count === 0;
  return (
    <div className="rounded-xl border bg-white p-5 text-sm space-y-2">
      <h3 className="text-lg font-semibold">{title}</h3>
      <p>Directory: {source.directory}</p>
      <p>Exists: {String(source.exists)}</p>
      <p>Supported files: {source.supported_count}</p>
      <p>Unreadable files: {source.unreadable_count}</p>
      <p>Formats: {formatList(source.formats)}</p>
      {empty ? <Notice>{emptyMessage}</Notice> : <Notice>{source.note}</Notice>}
    </div>
  );
}

function ArcadeSplitCard({ task, split, data }) {
  const holdout = split === "test";
  return (
    <article className="rounded-xl border bg-white p-4 text-sm space-y-1" aria-label={`${task} ${split} split`}>
      <h4 className="font-semibold">{task} / {split}{holdout ? " (holdout)" : ""}</h4>
      <p>Image files: {data.image_count}</p>
      {holdout ? <p>Annotations: not inspected; excluded from model selection.</p> : (
        <>
          <p>COCO annotations: {data.annotation_status === "available" ? data.annotation_count : data.annotation_status}</p>
          {data.annotation_image_count != null ? <p>Images listed in COCO: {data.annotation_image_count}</p> : null}
          {data.category_ids?.length ? <p>Category IDs: {data.category_ids.join(", ")}</p> : null}
        </>
      )}
      <Notice>{data.note}</Notice>
    </article>
  );
}

export default function DatasetPage() {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get("/api/dataset/summary")
      .then((res) => setSummary(res.data))
      .catch((err) => setError(apiError(err)));
  }, []);

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold">Dataset inspection</h2>
      {error ? <Notice tone="error">{error}</Notice> : null}
      {!error && !summary ? <Spinner label="Loading dataset summary..." /> : null}
      {summary ? (
        <>
          <div className="rounded-xl border bg-white p-5 text-sm space-y-2">
            <p>Total supported files: {summary.supported_count}</p>
            <p>Sample dataset: {summary.sample_supported_count}</p>
            <p>Uploaded case images: {summary.uploaded_supported_count}</p>
            <p>Unreadable files: {summary.unreadable_count}</p>
            <p>Formats: {formatList(summary.formats)}</p>
            <Notice>{summary.note}</Notice>
          </div>
          <SourceCard
            title="Sample dataset"
            source={summary.sample}
            emptyMessage="No sample images found"
          />
          <SourceCard
            title="Uploaded case images"
            source={summary.uploaded}
            emptyMessage="No accessible uploaded case images found"
          />
          <section className="space-y-3" aria-label="ARCADE dataset splits">
            <div>
              <h3 className="text-xl font-semibold">ARCADE dataset</h3>
              <p className="text-sm">Root: {summary.arcade.root} · {summary.arcade.exists ? "found" : "not found"}</p>
            </div>
            {Object.entries(summary.arcade.tasks || {}).map(([task, splits]) => (
              <div key={task} className="space-y-2">
                <h4 className="font-medium capitalize">{task}</h4>
                <div className="grid gap-3 md:grid-cols-3">
                  {Object.entries(splits).map(([split, data]) => (
                    <ArcadeSplitCard key={`${task}-${split}`} task={task} split={split} data={data} />
                  ))}
                </div>
              </div>
            ))}
          </section>
        </>
      ) : null}
    </div>
  );
}
