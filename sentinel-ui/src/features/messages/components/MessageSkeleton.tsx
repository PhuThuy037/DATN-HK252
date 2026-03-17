export function MessageSkeleton() {
  return (
    <div className="flex w-full justify-start">
      <div className="w-[70%] animate-pulse rounded-2xl rounded-bl-md border bg-muted/60 px-4 py-3">
        <div className="h-3 w-24 rounded bg-muted" />
        <div className="mt-2 h-3 w-full rounded bg-muted" />
        <div className="mt-2 h-3 w-2/3 rounded bg-muted" />
        <div className="mt-3 h-2 w-16 rounded bg-muted" />
      </div>
    </div>
  );
}
