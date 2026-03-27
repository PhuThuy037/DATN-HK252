export function MessageSkeleton() {
  return (
    <div className="flex w-full justify-start">
      <div className="w-[86%] max-w-[46rem] animate-pulse rounded-[24px] rounded-bl-lg border border-border/70 bg-muted/50 px-5 py-4">
        <div className="h-3 w-24 rounded bg-muted" />
        <div className="mt-3 h-3 w-full rounded bg-muted" />
        <div className="mt-2 h-3 w-2/3 rounded bg-muted" />
        <div className="mt-4 h-2 w-16 rounded bg-muted" />
      </div>
    </div>
  );
}
