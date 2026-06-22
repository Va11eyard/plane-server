# SSH keys for site audit (worker container mounts this as /root/.ssh)

Place here (chmod 600):

- `config` — Host aliases: proecta, wellmen-senai, pharma, odos
- private key (`id_ed25519` or `id_rsa`)

Copy from your laptop:

```bash
mkdir -p monitoring-ssh
scp ~/.ssh/id_ed25519 user@plane-server:/opt/plane-server/monitoring-ssh/
scp ~/.ssh/config user@plane-server:/opt/plane-server/monitoring-ssh/config
ssh plane "chmod 700 /opt/plane-server/monitoring-ssh && chmod 600 /opt/plane-server/monitoring-ssh/*"
```

Verify:

```bash
docker compose exec worker ssh -o BatchMode=yes proecta echo ok
```

Do not commit private keys to git.
