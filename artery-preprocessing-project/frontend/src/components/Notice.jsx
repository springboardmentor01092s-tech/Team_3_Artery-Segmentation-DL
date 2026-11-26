export default function Notice({ tone = "info", children }) {
  const tones = {
    info: "bg-teal-50 text-teal-900 border-teal-200",
    error: "bg-red-50 text-red-800 border-red-200",
    success: "bg-emerald-50 text-emerald-800 border-emerald-200",
  };
  return <div className={`rounded-lg border px-4 py-3 text-sm ${tones[tone]}`}>{children}</div>;
}
