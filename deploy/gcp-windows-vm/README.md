# Deploy to Google Cloud — Windows Server VM (with MT5)

This deploys AlphaBot FX (Streamlit dashboard + MT5 bridge + auto-update from
GitHub) to a Windows Server VM on Google Compute Engine.

> **Why a VM and not Cloud Run?** MetaTrader 5 only runs on Windows. Cloud Run
> uses Linux containers and cannot host the MT5 terminal. A small Windows GCE
> VM gives you cloud-hosted dashboard **and** working live execution.

---

## 1. Pre-reqs (one time, on your laptop)

```powershell
# gcloud SDK already installed; auth + select project
gcloud auth login
gcloud config set project project-d98f74d7-c53b-4552-8ba

# Enable required APIs
gcloud services enable compute.googleapis.com aiplatform.googleapis.com
```

---

## 2. Create the VM

Recommended machine type: **e2-standard-2** (2 vCPU, 8 GB RAM) — about $50/mo
on-demand, ~$25/mo with sustained-use discount. Spot-priced version is much
cheaper but can be preempted.

```powershell
gcloud compute instances create alphabot-vm `
    --project=project-d98f74d7-c53b-4552-8ba `
    --zone=us-central1-a `
    --machine-type=e2-standard-2 `
    --image-project=windows-cloud `
    --image-family=windows-2022 `
    --boot-disk-size=80GB `
    --boot-disk-type=pd-balanced `
    --tags=alphabot-streamlit
```

Open inbound port 8501 for Streamlit:

```powershell
gcloud compute firewall-rules create allow-alphabot-streamlit `
    --network=default `
    --allow=tcp:8501 `
    --target-tags=alphabot-streamlit `
    --source-ranges=0.0.0.0/0
```

> ⚠️ `0.0.0.0/0` exposes the dashboard to the internet (auth-protected, but
> still). Restrict to your home IP range if possible:
> `--source-ranges=YOUR_PUBLIC_IP/32`

---

## 3. RDP into the VM

```powershell
gcloud compute reset-windows-password alphabot-vm --zone=us-central1-a
# Save the username + password it prints, then RDP:
gcloud compute instances get-serial-port-output alphabot-vm --zone=us-central1-a
mstsc /v:<EXTERNAL_IP>
```

---

## 4. Run the bootstrap script (inside the VM, as Administrator)

Open PowerShell as Administrator on the VM and run:

```powershell
# Pull the bootstrap script straight from GitHub
$url = "https://raw.githubusercontent.com/msovo/alphafx/feature/multi-user-platform/deploy/gcp-windows-vm/startup.ps1"
Invoke-WebRequest -Uri $url -OutFile C:\startup.ps1
PowerShell -ExecutionPolicy Bypass -File C:\startup.ps1
```

This installs:

| Component             | Notes                                           |
|-----------------------|-------------------------------------------------|
| Chocolatey            | package manager                                 |
| Python 3.13           | system-wide                                     |
| Git, gcloud SDK, NSSM | for repo + service mgmt                         |
| MetaTrader 5          | silent install to default path                  |
| The repo              | cloned to `C:\alphabot-fx` on the chosen branch |
| Python venv + deps    | from `requirements.txt`                         |
| Windows firewall rule | port 8501 opened locally                        |
| `AlphaBotFX` service  | Streamlit running headless via NSSM, auto-start |
| Scheduled task        | `git pull` + service restart every 15 min       |

Total bootstrap time: ~10–15 minutes.

---

## 5. First-time configuration (inside the VM)

1. Launch **MetaTrader 5** once from the desktop and **log in** to your broker.
   This creates the local profile MT5 needs to accept programmatic connections.
2. Create your `.env` file at `C:\alphabot-fx\.env` (it's gitignored, so it
   never gets pushed):

   ```ini
   APP_ENV=production
   AI_BACKEND=vertex
   VERTEX_PROJECT=project-d98f74d7-c53b-4552-8ba
   VERTEX_LOCATION=us-central1
   ```

3. Set up Vertex AI auth on the VM (uses the GCE metadata service — no key
   files needed if the VM's default service account has the
   `roles/aiplatform.user` role). Grant it:

   ```powershell
   # Run from your laptop, not the VM
   $sa = (gcloud compute instances describe alphabot-vm `
          --zone=us-central1-a `
          --format="value(serviceAccounts[0].email)")
   gcloud projects add-iam-policy-binding project-d98f74d7-c53b-4552-8ba `
          --member="serviceAccount:$sa" --role="roles/aiplatform.user"
   ```

4. Restart the service:

   ```powershell
   Restart-Service AlphaBotFX
   ```

5. Browse to `http://<VM_EXTERNAL_IP>:8501`. Sign in with `nsovoadmin` /
   `Nsovo#07364@` (or register a fresh owner). On first login you'll be
   prompted to enter MT5 credentials — these are encrypted with Fernet
   (AES-128) and stored in `data/auth.db` on the VM.

---

## 6. Day-to-day

### Continuous deployment

You don't need a Cloud Build trigger — the VM auto-pulls from
`feature/multi-user-platform` every 15 minutes via Task Scheduler
(`AlphaBotAutoUpdate`). Just push to that branch:

```powershell
git push origin feature/multi-user-platform
```

Within 15 min the VM will `git reset --hard origin/<branch>`, reinstall deps if
`requirements.txt` changed, and restart the `AlphaBotFX` service.

### Manual update

```powershell
# On the VM
PowerShell -ExecutionPolicy Bypass `
    -File C:\alphabot-fx\deploy\gcp-windows-vm\auto-update.ps1
```

### Inspect logs

```powershell
Get-Content C:\alphabot-fx\logs\service-stderr.log -Tail 100
Get-Content C:\alphabot-fx\logs\service-stdout.log -Tail 100
Get-Service  AlphaBotFX
```

### Stop / start / restart

```powershell
Stop-Service    AlphaBotFX
Start-Service   AlphaBotFX
Restart-Service AlphaBotFX
```

---

## 7. Cost control

When you're not using it:

```powershell
# Stop the VM (no compute charge, only disk ~$3/mo)
gcloud compute instances stop alphabot-vm --zone=us-central1-a

# Start again
gcloud compute instances start alphabot-vm --zone=us-central1-a
```

---

## 8. Hardening checklist (do before going public)

- [ ] Restrict firewall `--source-ranges` to your IP only
- [ ] Put a reverse proxy (nginx / Caddy) with HTTPS in front of port 8501
- [ ] Use a custom domain via Cloud DNS + managed cert
- [ ] Move `data/.app_secret` to **Secret Manager** and read it at boot
- [ ] Rotate `nsovoadmin` password from the **Admin → Reset password** UI
- [ ] Enable **OS Login** + 2FA on the GCE side
- [ ] Snapshot the boot disk weekly (Compute → Snapshots)
