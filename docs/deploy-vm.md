# Deploy JELAI on a server

This guide installs JELAI on a new Ubuntu or Debian server (a VPS or a
cloud VM) with one script.

## Size of the server

| Resource | Minimum | Note |
|---|---|---|
| RAM | 8 GB | The hub, the middleware and Etherpad use about 2 to 3 GB. Each student notebook uses up to `NOTEBOOK_MEM_LIMIT` (the script sets 768M). With 8 GB, about 5 to 6 students can work at the same time. |
| CPU | 4 vCPU | A shared CPU is slow, but it is enough for a demo. |
| Disk | 40 GB | The Docker images need about 10 GB. |

The first build downloads the images and takes 10 to 20 minutes on a small
server. For a class of 20 students or more, use a server with 16 GB of RAM or
more, or set a lower `NOTEBOOK_MEM_LIMIT`.

## Steps

1. Make a server with Ubuntu 22.04 or 24.04 (or Debian 12) and log in as root with SSH.
2. Get an API key from an LLM provider. See [llm-providers.md](llm-providers.md).
   The server must be able to reach the LLM. An Open WebUI or Ollama server that
   only works inside a university network does not work from a server outside
   that network.
3. Run the script, with the LLM settings in front:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/mvallet91/JELAI/main/deploy/vm-setup.sh -o vm-setup.sh
   LLM_PROVIDER=groq LLM_API_KEY=your-key JUPYTERHUB_OPEN_SIGNUP=true bash vm-setup.sh
   ```

   To install a branch that is not `main`, add `BRANCH=<branch name>`.
   For an Open WebUI server, use `LLM_PROVIDER=openwebui LLM_BASE_URL=https://... LLM_API_KEY=... LLM_MODEL=...`.
4. Open port 8000 in the firewall of the server (in the control panel of the provider).
5. Open `http://<server IP>:8000`, sign up as `admin`, and log in.

The script prints the teacher password at the end. It is also in
`/opt/jelai/jupyterhub-docker/.env`.

## Teacher pages

By default, the teacher pages are not open to the internet. Use an SSH tunnel
from your computer:

```bash
ssh -L 8004:localhost:8004 root@<server IP>
```

Then open `http://localhost:8004/teacher-settings` and
`http://localhost:8004/teacher-view`. To open port 8004 to everyone, run the
script with `TEACHER_PUBLIC=true`.

## Security

- The system uses HTTP without encryption. Passwords go over the network in
  plain text. Use it for a demo, with passwords that you do not use anywhere
  else. For a real class, put a reverse proxy with HTTPS (for example Caddy)
  in front of port 8000.
- Docker ignores the `ufw` firewall for the ports that it publishes. Use the
  firewall of the provider to close ports.
- The hub has access to the Docker socket of the server. Do not run other
  services with secrets on the same server.

## Update and stop

```bash
cd /opt/jelai && git pull && cd jupyterhub-docker && docker compose build && docker compose up -d
docker compose down        # stop. The data stays in Docker volumes.
docker compose logs -f middleware
```
