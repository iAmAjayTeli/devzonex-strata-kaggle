# 🚀 Strata on Kaggle — by DevZoneX

[![Tests](https://github.com/iAmAjayTeli/devzonex-strata-kaggle/actions/workflows/tests.yml/badge.svg)](https://github.com/iAmAjayTeli/devzonex-strata-kaggle/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
![Platform](https://img.shields.io/badge/platform-Kaggle%20GPU-20BEFF)
![Status](https://img.shields.io/badge/status-experimental-orange)

**Run a Strata-supported model on a Kaggle GPU, cache the model and Strata runtime in your own private Kaggle Datasets, and connect OpenCode Desktop through a temporary authenticated HTTPS tunnel.**

This project turns the manual setup we used for Strata + Qwen3.8-Flash-Next Gyro-S on two Tesla T4 GPUs into a guided Kaggle notebook. The default example is `gyro / gyro-s`; you can change the family and variant to another combination supported by the installed Strata release.

> [!WARNING]
> **Experimental project.** The helper scripts and notebook are included, but the complete first-run and fresh-session workflow still needs validation on more Kaggle accounts/GPU configurations. Review the Strata plan before approving large downloads. Kaggle availability, quotas, GPU types, model licenses, and Strata compatibility vary.

---

## ✨ What it does

| Stage | What happens |
|---|---|
| **1 · Preflight** | Checks Kaggle Secrets, Internet, GPU visibility, attached datasets, and Strata version. |
| **2 · Choose a model** | Lets you choose a Strata-supported family, variant, context, vision option, and GPUs. |
| **3 · Restore or install** | Restores your private runtime/model caches when attached, otherwise installs Strata and lets Strata fetch the needed files. |
| **4 · Plan before download** | Runs Strata's plan command so you can review the selected model/engine before the large first download. |
| **5 · Start securely** | Starts Strata in Cloudflare access mode, creates/reuses a temporary Cloudflare Quick Tunnel, and checks the health endpoint. |
| **6 · Verify access** | Confirms no-key API requests are rejected, authenticated model listing works, and a short chat completion succeeds. |
| **7 · Save your caches** | Optionally uploads model data and the Strata terminal/engine into **separate, private datasets owned by you**. |
| **8 · Connect OpenCode** | Prints the current temporary HTTPS base URL, model ID, and a provider snippet that references a local key file rather than embedding the key. |

### What is still manual?

Kaggle requires you to enable GPU/Internet, add notebook Secrets, and attach datasets from the Kaggle UI. The notebook cannot bypass those account controls or grant access to datasets you don't own. The first download and private dataset upload can take a long time, especially for models around 80 GiB or larger.

## 🧭 Quick links

- **[Open the Kaggle launcher notebook](notebooks/Strata_Kaggle_Launcher.ipynb)**
- [Kaggle setup checklist](docs/kaggle-setup.md)
- [OpenCode connection guide](docs/opencode-setup.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Security policy](SECURITY.md)
- [Strata official setup guide](https://github.com/Niko1221/Strata/blob/main/docs/AI_SETUP.md)
- [Strata model compatibility guide](https://github.com/Niko1221/Strata/blob/main/docs/MODELS.md)

---

## ✅ Before you start

You need:

- A Kaggle account with notebook Internet access and an available compatible GPU accelerator.
- A Kaggle API token stored as a **Kaggle Notebook Secret**.
- Your Kaggle username (spelled exactly as in your profile).
- Enough available session time, disk space, and Kaggle dataset quota for the selected model and its supporting files.
- A model whose terms allow you to download and use it. If you plan to cache the files, the terms must also allow you to keep a private copy.
- An OpenCode Desktop installation if you want to use the model through OpenCode on Windows.

### Important compatibility rule

This project is **not** a universal Hugging Face model runner. Strata supports specific families, variants, packs, formats, and hardware combinations. A model being downloadable from a model hub does not mean Strata can run it. Select a family/variant accepted by Strata and trust the plan output—not a guessed model name.

The default example from our working setup:

```python
MODEL_FAMILY = "gyro"
MODEL_VARIANT = "gyro-s"
CONTEXT = "32k"
VISION = "off"
```

Keep the first test text-only. Vision and other advanced features can be configured separately after the basic server works.

---

# 🧑‍💻 First-time setup — full walkthrough

## Step 1 — Open the notebook in Kaggle

1. Open [`notebooks/Strata_Kaggle_Launcher.ipynb`](notebooks/Strata_Kaggle_Launcher.ipynb) in GitHub.
2. Download the `.ipynb` file, then use Kaggle's **New Notebook / Import Notebook** flow to import it. Alternatively, create a blank Kaggle notebook and copy the notebook cells in order.
3. In the notebook settings, enable **Internet** and select an available NVIDIA GPU accelerator.
4. Save the notebook.

If Kaggle asks you to restart after changing the accelerator or Internet setting, restart the notebook before running cells. GPU availability and session limits depend on Kaggle's current policies and your account.

## Step 2 — Create a Kaggle API token and save it as a Secret

1. Open your Kaggle account settings and create an API token using Kaggle's current instructions.
2. Open the notebook's **Add-ons → Secrets** panel.
3. Add a secret named exactly:

   ```text
   KAGGLE_API_TOKEN
   ```

4. Paste the token as the secret value and grant this notebook permission to read it.
5. Never paste the token into a notebook code cell, a public GitHub file, a screenshot, or this chat.

The notebook reads the secret through Kaggle's `UserSecretsClient`. It writes the token to a restricted temporary configuration directory for CLI upload commands and does not intentionally print the token.

## Step 3 — Set the model and cache configuration

Run the notebook's **USER CONFIGURATION** cell. Set your own Kaggle username and the model you want Strata to run.

Example:

```python
KAGGLE_USERNAME = "your-kaggle-username"

MODEL_FAMILY = "gyro"
MODEL_VARIANT = "gyro-s"
CONTEXT = "32k"
VISION = "off"

GPU_IDS = ""  # blank = automatically detect visible NVIDIA GPUs
MODEL_DATA_DIR = "/root/strata-local"

UPLOAD_CACHES = True
I_CONFIRM_MODEL_LICENSE_AND_PRIVATE_STORAGE = False
FORCE_UPDATE_MODEL_CACHE = False
FORCE_UPDATE_RUNTIME_CACHE = False
```

**Do not leave `KAGGLE_USERNAME` set to the placeholder.** The notebook derives the dataset slugs from the username/model choice.

For the default choice, the notebook uses:

- Model cache slug: `strata-model-gyro-gyro-s`
- Runtime cache slug: `strata-runtime-cache`

These are separate datasets. Do not use someone else's private dataset slug unless that dataset has explicitly been shared with you.

### Model-cache upload consent

The default setting is deliberately:

```python
I_CONFIRM_MODEL_LICENSE_AND_PRIVATE_STORAGE = False
```

Leave it `False` until you've checked the model's license and confirmed that creating a private copy in your Kaggle Dataset is allowed. If it remains `False`, the notebook skips the model-cache upload; the runtime cache can still be saved. Never upload model weights to GitHub.

## Step 4 — Run the notebook from top to bottom

Run each cell in order. The notebook is designed for this flow:

1. **Load helpers and credentials:** clones this repository's helper scripts and reads your secret.
2. **Restore caches:** if your own model/runtime cache datasets are attached, verifies and restores them. If this is the first run, it installs Strata instead.
3. **Review the Strata plan:** runs a plan for the chosen family/model/context/vision/GPU combination. Read the output before continuing.
4. **Launch Strata:** if the chosen files are not present, Strata may download the model and a compatible engine. That first download can be large.
5. **Start/verify the tunnel:** the notebook checks the local health endpoint, requires Strata API-key protection, starts Cloudflare Tunnel if Strata hasn't provided an HTTPS URL, and verifies the public API.
6. **Run a short generation test:** it sends an authenticated request and confirms the response.
7. **Upload caches:** after a working launch, it can upload the model files and the Strata terminal/engine to separate private Kaggle datasets.

### Expected checks

Before the notebook says the endpoint is ready, it should verify:

- Strata health says the model is loaded.
- The local health response indicates API-key protection is enabled.
- An unauthenticated request to `/v1/models` returns HTTP `401` or `403`.
- An authenticated request to `/v1/models` succeeds.
- A short authenticated `/v1/chat/completions` request returns text.

If the unauthenticated request succeeds with HTTP `200`, **do not use the public tunnel**. Stop the tunnel and fix Strata's authentication before continuing.

## Step 5 — Wait for your private Kaggle datasets to finish processing

The notebook will try to create or update:

| Dataset | Contents | When it is used |
|---|---|---|
| `<your-username>/strata-model-<family>-<variant>` | Model files and support files plus a manifest that maps uploaded files back to their paths | Avoid re-downloading the same model from its original source on a later session |
| `<your-username>/strata-runtime-cache` | Strata terminal, engine components, manifest, checksum and (when installed) the Cloudflare Tunnel binary | Avoid re-downloading the same compatible terminal/engine build |

The datasets are created without a public-visibility flag and are intended to remain **private**. Still verify the visibility and file list on Kaggle after upload. A successful file transfer is not the same as Kaggle finishing dataset creation; wait for processing to complete.

Large dataset uploads can fail because of account limits, model terms, insufficient disk space, or network/session interruptions. The notebook cannot guarantee that every model fits the selected GPU or that every upload will be accepted.

---

# 🔁 Restarting in a later Kaggle session

This is where the caches help. Files under `/root` are temporary and should not be expected to survive a full Kaggle runtime reset.

1. Open the same Kaggle notebook.
2. Enable Internet and select a compatible GPU.
3. Open **Add Input** and attach **your own** model cache and runtime cache datasets.
4. Ensure the `KAGGLE_API_TOKEN` Secret is available to this notebook.
5. Keep the username and model family/variant consistent with the cache dataset slugs.
6. Run the cells from the top.

The notebook looks for:

- `/kaggle/input/datasets/<username>/strata-model-<family>-<variant>/manifest.json`
- `/kaggle/input/datasets/<username>/strata-runtime-cache/strata-runtime-cache.bin`
- `strata-runtime-cache.bin.sha256`
- `runtime-manifest.json`

It verifies sizes/checksums and restores the runtime and model files into local storage. **A restore from Kaggle's read-only dataset mount still copies the data into local storage and can take several minutes.** The benefit is avoiding downloads from the original model host and Strata's engine feed—not eliminating all data movement.

A runtime cache can become incompatible if Strata, the engine, the operating environment, or the GPU changes. Review the Strata plan and let Strata fetch a compatible engine when needed.

---

# 🖥️ Connect OpenCode Desktop

When the notebook prints the connection information:

1. Copy the current HTTPS URL. It is temporary and can change after a restart.
2. In the Kaggle shell, retrieve the Strata key privately with:

   ```bash
   strata launch --show-key
   ```

3. On Windows, save the key locally at:

   ```text
   %USERPROFILE%\.config\opencode\strata-key.txt
   ```

   Do **not** put the actual key in `opencode.jsonc`, GitHub, notebook output, or chat. OpenCode must be able to read the local key file; verify that the file-substitution syntax shown in the notebook matches your installed OpenCode version.

4. Merge the provider snippet printed by the notebook into the existing top-level `providers` object in `opencode.jsonc`. Don't overwrite your other provider/MCP settings.
5. Set your selected model to the provider/model name printed by the notebook and restart OpenCode.
6. Start a fresh OpenCode session and test with: `Reply with exactly: Strata connection working.`

### Keep these running

- The Kaggle session and Strata server.
- The Cloudflare `cloudflared` tunnel process.
- The Internet connection for the Kaggle runtime.

Cloudflare Quick Tunnels provide a **temporary public HTTPS URL**, not a permanent endpoint. Anyone who obtains the URL can reach the service, so the API key must be enforced and kept private. If the Kaggle session/tunnel stops, the URL can become unavailable or change. Update OpenCode with the new URL after restarting.

---

## 🔐 Security and licensing

- Never commit API keys, Kaggle tokens, access-token files, local OpenCode secret files, model weights, or runtime archives.
- Keep the model and runtime Kaggle Datasets private. Review the Kaggle UI after creation.
- The tunnel is publicly reachable; API-key protection is required. Verify that unauthenticated requests are rejected before using it.
- Stop Strata and the tunnel when finished. This is an experimental temporary server, not a production hosting service.
- Check the model's terms before downloading, modifying, or uploading it—even to a private dataset. Private upload is not automatically permitted for every model.
- The repository's MIT license applies to **original code and documentation in this repository only**. Strata, its engine, model weights and other third-party software retain their own licenses and terms.
- Kaggle GPUs, session durations, Internet access, storage and dataset quotas depend on Kaggle's current policies/account availability; this project does not bypass those rules.

---

## 🛠️ Troubleshooting

| Problem | What to check |
|---|---|
| **No GPU detected** | Enable a GPU accelerator in Kaggle settings and restart the notebook if requested. Check `nvidia-smi`. |
| **Kaggle Secret missing** | Confirm the secret is named exactly `KAGGLE_API_TOKEN` and notebook access is enabled. Do not print the secret for debugging. |
| **Dataset not found** | Attach the dataset through **Add Input** and verify the Kaggle username/slug match the configuration cell. |
| **403 from Kaggle API** | Verify the token/account/dataset access and whether Kaggle has finished processing the dataset. Don't immediately re-upload a large archive. |
| **Strata rejects the model** | Choose a family/variant listed by the installed Strata release; run the plan again before downloading. A model name from a hub is not sufficient. |
| **Model download too large/slow** | Check free local space, session time remaining, Internet, and the model's license/size. Try a smaller compatible variant if necessary. |
| **Cache upload skipped** | For model uploads, ensure license confirmation is explicitly enabled. Check the upload logs and Kaggle dataset page. |
| **Runtime cache won't restore** | Verify the runtime dataset is attached and contains `strata-runtime-cache.bin`, `strata-runtime-cache.bin.sha256`, and `runtime-manifest.json`. Check the checksum and environment compatibility. |
| **Tunnel URL won't load** | Verify Strata health locally, then check that `cloudflared` is running and the log shows a registered connection. Use the current URL, not one from an old session. |
| **OpenCode gets 401** | Key missing/incorrect or auth header not sent. Check the local key file and provider settings without printing the value. |
| **OpenCode hangs** | Test authenticated `/v1/models` and `/v1/chat/completions` independently. Check Strata/tunnel logs and confirm the provider context limit matches the real context. |

For more details, see [the troubleshooting guide](docs/troubleshooting.md).

---

## 🧪 Development and tests

The repository includes helper unit tests and a GitHub Actions workflow that checks Python syntax and runs pytest.

To run tests locally:

```bash
python -m pip install --upgrade pytest
python -m compileall -q scripts tests
python -m pytest -q
```

These tests do not replace the required fresh Kaggle integration test. Before calling the project “fully tested,” validate first launch, private dataset creation, a fresh-session cache restore, API-key rejection, authenticated generation, and OpenCode connectivity.

## 🤝 Contributing

Please include the Strata version, GPU name, whether this was a first-time launch or cache restore, and the exact error with secrets removed. Do not upload model files, API keys, Kaggle credentials, or notebook outputs containing secrets in issues or pull requests.

## 📄 License

Original project code and docs: [MIT](LICENSE). Third-party components and model assets retain their respective licenses.
