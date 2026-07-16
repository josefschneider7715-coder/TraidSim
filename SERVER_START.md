# Serverstart

## Windows-Server

`start_windows.bat` per Doppelklick oder Aufgabenplanung starten.

Die App laeuft danach unter:

```text
http://SERVER-IP:8501
```

## Linux-Server

```bash
chmod +x start_server_linux.sh
./start_server_linux.sh
```

Die App bindet auf `0.0.0.0:8501` und ist damit ueber die Server-IP erreichbar.

## Hinweis

Port `8501` muss in Firewall/Router erlaubt sein. Fuer oeffentlichen Betrieb spaeter HTTPS ueber Nginx oder Caddy davor setzen.
