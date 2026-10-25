# Troubleshooting

## Model family or variant is unsupported

Run `strata launch --plan --family FAMILY --model VARIANT` and choose a combination accepted by the installed Strata release. Not every Hugging Face model is compatible with Strata.

## Runtime cache doesn't restore

Attach your private runtime dataset via Add Input and verify that it contains `strata-runtime-cache.tar`, `strata-runtime-cache.tar.sha256`, and `runtime-manifest.json`. The notebook verifies the checksum before extraction.

## Model files are missing

Attach your private model dataset. It should contain `manifest.json` and numbered flattened files. The notebook restores files to the paths named in the manifest and verifies sizes.

## Dataset upload permissions fail

Check that the Kaggle Secret is named `KAGGLE_API_TOKEN`, that notebook access is enabled, and that `KAGGLE_USERNAME` matches the account which owns the dataset. Dataset creation can take additional time after the file upload is complete.

## API key test fails

The public `/v1/models` endpoint must reject unauthenticated requests with HTTP 401/403. Do not continue with a public tunnel if it returns a successful unauthenticated response. Check Strata's access mode and restart it with `--access cloudflare`.

## Cloudflare URL times out or changes

A Quick Tunnel only exists while its process/session is active. Read the latest URL from the notebook output and update OpenCode. Keep the Kaggle runtime running.

## Slow or early OpenCode compaction

Check the OpenCode provider model's `limit.context` and `limit.output` against Strata's actual context. Start a fresh OpenCode session after changing compaction settings. For short tests, use `reasoning_effort: none`.
