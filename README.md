# papermill kubernetes job progress

This is a papermill engine which annotates a kubernetes job with its progress.

~~After each cell has been executed, it calls the kubernetes patch job api endpoint for the job `$JOB_NAME` and sets the 
annotation `$PROGRESS_ANNOTATION` to a number between 0 and 100 (percentage of cells already executed).~~

Note: This fork has been modified to use a NATS.io message bus to send the progress messages.

## Configuration

This engine assumes there is a NATS server configured and reachable. To configure the plugin, set the following 
envvars:

`NOTEBOOK_ID_ENV_KEY`: The environment variable key that contains the JOB_ID to be sent in a progress message. For example, 
if an environment variable named `NOTEBOOK_ID` is set that contains the notebook ID, set this value to the string 
`NOTEBOOK_ID`, and the plugin will try to resolve `os.environ['NOTEBOOK_ID']` when running.

`NATS_URL`: URL to the NATS server to connect to

`NATS_USER`: Username used to connect to NATS

`NATS_PASSWORD`: Password used to connect to NATS

`NATS_SUBJECT`: The subject to publish messages on. Defaults to "progress"


## Testing

Invoke as follows:

```
papermill --engine kubernetes_job_progress test.ipynb output.ipynb
```

