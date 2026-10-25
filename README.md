# DevZoneX — Strata on Kaggle

Run Strata-supported local models on a Kaggle GPU notebook and connect OpenCode through a temporary authenticated HTTPS tunnel.

> **Status: experimental.** Validate in a fresh Kaggle session before relying on this workflow. Kaggle sessions are temporary, model downloads can be large, and not every Hugging Face model is compatible with Strata. Use only model files you have permission to download, store, and use.

## What this project aims to automate

1. Check the Kaggle runtime, GPU, internet setting, attached datasets, and required secrets.
2. Select a Strata-supported model family/variant and run a plan/preflight before downloading large files.
3. Download model files through Strata or its supported model workflow and verify them.
4. Save model artifacts to a **private, user-owned Kaggle Dataset** when the user has configured Kaggle API access.
5. Install or restore the Strata terminal and compatible engine, then optionally save them to a separate private runtime-cache dataset.
6. Start Strata with API-key access, create a temporary Cloudflare Quick Tunnel, and verify that unauthenticated requests are rejected and authenticated API requests succeed.
7. Print OpenCode provider instructions without printing secrets.

The notebook cannot attach datasets or create/add Kaggle Secrets on a user's behalf. Those are manual Kaggle UI steps. Kaggle may require the user to restart a session after changing accelerator/internet settings. Dataset uploads and processing can take time.

## Quick start

1. Open `notebooks/Strata_Kaggle_Launcher.ipynb` in Kaggle (or import it into a new Kaggle notebook).
2. Enable a compatible GPU and internet access, subject to your account's Kaggle quotas and policies.
3. If resuming a previous run, attach your own model-cache and runtime-cache datasets under **Add Input**.
4. Add any required API token to Kaggle Secrets; never paste it into notebook cells, output, GitHub, or this README.
5. Execute the notebook cells from top to bottom. Review the Strata launch plan before confirming a large download.
6. When prompted, confirm the model's license permits your intended use and private cache upload.
7. Copy the generated temporary HTTPS base URL and follow the OpenCode instructions. Keep the API key private.

## Model selection and compatibility

Strata supports specific engine/model families and variants. A Hugging Face repository being downloadable does **not** mean Strata can run it. Use the Strata plan/preflight and supported model list for the selected Strata release. The notebook should fail early rather than download a large model for an unsupported selection. The default example is `gyro / gyro-s`, matching the tested DevZoneX setup; it is not a promise that every GPU or Kaggle session can fit every model.

## Cache design

- **Model cache dataset:** model weights and support files, private to the user. Large uploads may be constrained by Kaggle Dataset rules, processing time, quotas, and model terms.
- **Runtime cache dataset:** Strata terminal and engine components, private to the user. Restore only builds compatible with the current OS, GPU, CUDA/driver environment, and Strata version. Re-run plan/preflight and fetch compatible components when uncertain.
- Do not put API keys, Kaggle tokens, tunnel credentials, or local credential files in either dataset.

## Remote-access safety

Cloudflare Quick Tunnels are temporary public URLs; anyone who obtains a URL can reach the exposed service. Strata must enforce its API key. Verify the unauthenticated `/v1/models` request returns `401` or `403` before using the tunnel. Then perform a short authenticated test request. Never print or commit the API key. Stop the tunnel and Strata when finished. Do not use this as a permanent production endpoint.

## OpenCode

Use a custom OpenAI-compatible provider whose `baseURL` is the current tunnel URL with `/v1` appended and whose API key is read locally by OpenCode from a user-owned secret file or environment variable. The Quick Tunnel URL changes after tunnel restarts, so update the provider base URL each time it changes. OpenCode's configuration format/package identifiers can vary between releases; follow the documentation for your installed version and validate the JSON before restarting.

## Troubleshooting

- **Dataset path missing:** attach the dataset in Kaggle's Add Input panel and inspect `/kaggle/input`.
- **403 from Kaggle API:** verify the dataset has finished creation, the token is valid, and your account has access. Do not re-upload just because a file-list API call temporarily returns 403.
- **Strata downloads runtime repeatedly:** inspect the installed terminal/engine locations and ensure runtime cache was created from the same compatible build. Compare checksums before extracting.
- **Model launch slow from dataset mount:** use local working storage when available and verify disk space, then copy/reuse cached files. Do not assume `/root` persists after a runtime reset.
- **Tunnel URL unreachable:** confirm Strata and cloudflared are running, the local health endpoint works, and the tunnel log shows a registered connection.
- **OpenCode stalls:** first test the authenticated `/v1/models` and `/v1/chat/completions` APIs independently; inspect server and tunnel logs without printing credentials.

## Contributing

Please include the Strata version, GPU type, exact error message with secrets removed, and whether the failure happened during first-time setup or restore. Never upload model weights or credentials in an issue or pull request.

## License

Original project scripts and documentation are released under the MIT License. That license does not apply to Strata, model weights, or other third-party software; each retains its own terms.