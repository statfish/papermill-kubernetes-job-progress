# papermill kubernetes job progress

This is a papermill engine which annotates a kubernetes job with its progress.

After each cell has been executed, it calls the kubernetes patch job api endpoint for the job `$JOB_NAME` and sets the annotation `$PROGRESS_ANNOTATION` to a number between 0 and 100 (percentage of cells already executed).
