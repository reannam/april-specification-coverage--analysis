type StatusPanelProps = {
  status: "processing" | "error" | "success";
  message: string;
  progress?: number;
};

export default function StatusPanel({
  status,
  message,
  progress,
}: StatusPanelProps) {
  const measuredProgress =
    progress === undefined ? null : Math.min(100, Math.max(0, progress));

  return (
    <div className={`status-panel ${status}`}>
      <strong>
        {status === "processing"
          ? "Processing"
          : status === "success"
            ? "Complete"
            : "Something went wrong"}
      </strong>
      <p>{message}</p>
      {status === "processing" ? (
        <div
          aria-label={
            measuredProgress === null
              ? "Processing; completion percentage is not available"
              : `${Math.round(measuredProgress)}% complete`
          }
          aria-valuemax={measuredProgress === null ? undefined : 100}
          aria-valuemin={measuredProgress === null ? undefined : 0}
          aria-valuenow={
            measuredProgress === null ? undefined : Math.round(measuredProgress)
          }
          className={`progress ${measuredProgress === null ? "indeterminate" : ""}`}
          role="progressbar"
        >
          <span
            style={
              measuredProgress === null
                ? undefined
                : { width: `${measuredProgress}%` }
            }
          />
        </div>
      ) : null}
    </div>
  );
}
