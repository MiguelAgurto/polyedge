"use client";
export default function Error({
  error,
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  return (
    <div className="rounded border border-red-900 bg-red-950/20 p-6">
      <h1 className="text-lg font-semibold">Data could not be loaded</h1>
      <p className="muted mt-2 text-sm">{error.message}</p>
      <button onClick={reset} className="accent mt-5 cursor-pointer text-sm">
        Retry
      </button>
    </div>
  );
}
