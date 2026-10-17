# Etherpad API key

`setup.sh` writes a random API key to `APIKEY.txt` in this directory.
Etherpad, the middleware and the student notebooks read the key from this file.
The file is a secret, so git ignores it.

To make the key without `setup.sh`:

```bash
openssl rand -hex 32 > jupyterhub-docker/etherpad/APIKEY.txt
```
