# Troubleshooting

## Model family or variant is unsupported

Run the notebook's Strata plan cell and choose a family/variant accepted by the installed Strata release. Not every Hugging Face model is compatible with Strata. Review the plan before approving large downloads.

## Runtime cache doesn't restore

Attach your private runtime dataset through **Add Input** and verify that it contains:

- `strata-runtime-cache.bin`
- `strata-runtime-cache.bin.sha256`
- `runtime-manifest.json`

The notebook verifies the checksum before extracting the archive. The runtime archive filename ends in `.bin` intentionally so Kaggle doesn't automatically unpack the tar archive during dataset creation.

The current helper safely rewrites absolute symlinks recorded inside the Strata runtime archive (such as `terminal/current`) into relative links during extraction. It still rejects links that point outside the Strata runtime root or cross between `terminal/`, `components/`, and `tools/`. If an existing notebook still raises `Unsafe absolute link in runtime archive`, rerun **Load helper scripts and Kaggle credentials** so it reloads the latest helper from GitHub.

If the cached Strata/engine build doesn't match the runtime, the helper may skip or replace the cached restore and install/fetch a compatible version. Don't assume an older engine is compatible with every Strata release or GPU.

## Model files are missing or the model appears to download again

Attach your private model dataset. It should contain `manifest.json` and numbered flattened files. The notebook uses the manifest to reconstruct the model paths.

- `MODEL_RESTORE_MODE = "symlink"` creates links under `/root/strata-local` to the mounted, read-only Kaggle input files, avoiding a second full local copy. Direct reads may be slower.
- `MODEL_RESTORE_MODE = "copy"` copies the files into local storage. This takes extra time/disk space but may improve model loading and reads.

**Why Add Input shows a download percentage:** Kaggle stages the attached dataset into the new runtime. For an 80-GiB model it can show progress such as `Downloaded 14/16 files: 4.5 GiB / 79.94 GiB`. This is a transfer from your Kaggle Dataset storage, not necessarily a download from the original model host. Wait until staging and the restore cell finish. If the model cache restore returns `False`, verify that the dataset slug, username and manifest match your configuration before running Strata.

## Cache upload appears frozen

The notebook helper now streams Strata and Kaggle CLI output and prints periodic status while long commands run. If a cell only shows `Preparing ... files`, it may be using a helper that was imported before the latest update.

1. Do not interrupt an upload that is still transferring files.
2. After the current attempt has finished (or if it failed), rerun **Load helper scripts and Kaggle credentials** to pull and reload the latest helper code.
3. Rerun only the cache-upload cell if needed. Check Kaggle's dataset page/version before trying another upload.

A 79.94-GiB model upload can take a long time. An output line saying `Dataset is being created` means the transfer was submitted; it does not prove dataset processing has completed.

## Kaggle dataset slug already exists

The helper attempts to create a dataset first. If the requested slug already exists, it should upload a new dataset version rather than create a duplicate. Wait for processing to finish and confirm the intended Version page in the Kaggle UI before repeating the command.

## Dataset upload permissions fail

Check that the Kaggle Secret is named exactly `KAGGLE_API_TOKEN`, notebook access is enabled, and `KAGGLE_USERNAME` matches the account that owns the dataset. Dataset processing can continue after all files have been uploaded. Verify dataset visibility and ownership in Kaggle.

## API key test fails

The public `/v1/models` endpoint must reject unauthenticated requests with HTTP `401` or `403`. Do not continue using a public tunnel if the unauthenticated request succeeds. Check Strata's access mode and use `--access cloudflare`.

Never paste the API key into notebook output, GitHub, issues, or chat.

## Cloudflare URL times out or changes

A Quick Tunnel exists only while its process/session is active. Use the latest HTTPS URL printed by the notebook, check the Cloudflare log if needed, and update OpenCode's `baseURL`. Keep the Kaggle runtime and tunnel process running while using the model.

## OpenCode returns 401 or hangs

- For `401`, check the local key file and OpenCode provider settings without printing the key.
- Test the authenticated `/v1/models` and `/v1/chat/completions` endpoints independently before troubleshooting OpenCode.
- Confirm the configured context/output limits match the running Strata model. After changing compaction/provider settings, start a fresh OpenCode session.

## Six-hour monitor doesn't complete

The monitor checks local model health and the tunnel's no-key authentication boundary. It does not override Kaggle session limits, quotas, network outages, or runtime shutdown. A notebook may end before six hours if the platform or account limit is reached.
