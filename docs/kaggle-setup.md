# Kaggle setup checklist

## First run

- [ ] Open `notebooks/Strata_Kaggle_Launcher.ipynb` from the repository in Kaggle.
- [ ] Turn on Internet and select an available GPU accelerator.
- [ ] Add `KAGGLE_API_TOKEN` under Add-ons → Secrets and grant access to the notebook.
- [ ] Enter your exact Kaggle username in the configuration cell.
- [ ] Choose a Strata-supported `MODEL_FAMILY` and `MODEL_VARIANT`.
- [ ] Run the plan cell and review its output before launching.
- [ ] Review model terms. Only then enable private model caching in the configuration cell.
- [ ] Wait for the API test and dataset uploads to report success.
- [ ] Verify both datasets on Kaggle and keep them private.

## Subsequent runs

- [ ] Start a fresh Kaggle session.
- [ ] Attach the model and runtime datasets you own via Add Input.
- [ ] Enable the Kaggle API Secret for this notebook.
- [ ] Run the notebook in order.
- [ ] Update OpenCode's base URL if a new Quick Tunnel URL is printed.

## Notes

- The model data and terminal/engine runtime use separate private datasets.
- The first launch downloads model data and the matching engine; they are saved after Strata starts.
- Restoring an attached model dataset copies files from Kaggle's read-only mount into local /root storage. This avoids downloading the original model again, but copying a very large model can still take several minutes.
- A Quick Tunnel is temporary, publicly reachable, and does not replace API-key authentication.
