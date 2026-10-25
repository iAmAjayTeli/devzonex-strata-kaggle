# Kaggle setup — full checklist

The quickest entry point is the **Open in Kaggle** badge at the top of the [repository README](../README.md). It imports the public notebook into Kaggle; it cannot grant access to private datasets or secrets.

## First run: download and cache

- [ ] Open `notebooks/Strata_Kaggle_Launcher.ipynb` in Kaggle using the badge or **New Notebook → Load from URL**.
- [ ] Enable Internet and select an available NVIDIA GPU accelerator. Restart the runtime if Kaggle asks you to.
- [ ] Add a secret named `KAGGLE_API_TOKEN` under **Add-ons → Secrets** and enable notebook access.
- [ ] In the configuration cell, replace `your-kaggle-username` and choose a Strata-supported `MODEL_FAMILY` and `MODEL_VARIANT`.
- [ ] Start with the default `gyro / gyro-s` example if you want to reproduce the setup documented in this repo.
- [ ] Review the model license. Keep `I_CONFIRM_MODEL_LICENSE_AND_PRIVATE_STORAGE = False` until private caching is allowed for your selected model.
- [ ] Run the notebook cells from top to bottom; review the Strata plan before the large download.
- [ ] Confirm local health says the model is loaded, and verify unauthenticated requests are rejected (401/403) before using a public tunnel.
- [ ] After the authenticated chat test succeeds, run the cache-upload cell. The helper uploads model data only when the explicit license confirmation is true and uploads the runtime to a separate private dataset.
- [ ] Wait for Kaggle to finish processing both dataset uploads before ending the session.

## Returning run: restore caches

- [ ] Start a fresh session using the same notebook.
- [ ] Enable Internet/GPU and grant the notebook access to `KAGGLE_API_TOKEN`.
- [ ] Use **Add Input** to attach your own model cache and runtime cache datasets. The cache names are printed by the notebook configuration cell.
- [ ] Keep the Kaggle username, model family and variant consistent with the attached cache names.
- [ ] Run the notebook from top to bottom.
- [ ] Confirm `Runtime cache restored: True` and `Model cache restored: True` before launching Strata.
- [ ] Confirm the runtime checksum, health check and authenticated public API test all pass.

## Why does Add Input show a download?

Attaching a dataset makes files available to a new Kaggle runtime. Kaggle may show a notification such as `Downloaded 14/16 files: ... GiB / ... GiB`; that's the input data being staged from your Kaggle Dataset storage into the session, not a download from the original model host.

The notebook's `MODEL_RESTORE_MODE` defaults to `"symlink"`, which links into the read-only input mount and avoids a second full local copy. Reads may be slower. Set `MODEL_RESTORE_MODE = "copy"` when local model reads are too slow; this uses extra time and disk space but copies files to `/root/strata-local`.

No restore mode eliminates Kaggle's input staging or guarantees instant startup. The cache prevents the original-source model download when the attached files match the requested model; it does not turn the dataset into a permanently attached disk across all sessions.

## Manual account steps

Kaggle controls GPU selection, Internet access, Secrets, dataset visibility, and dataset sharing in its UI. The notebook does not create a secret for you or attach datasets on your behalf. Private datasets are only available to their owner and users with access granted by that owner.

## Six-hour monitoring

After launch and successful API verification, run the optional supervision cell. It checks the model health and tunnel/auth boundary for up to six hours. This does not override Kaggle's execution limits, quotas, inactivity behavior, or service failures.
