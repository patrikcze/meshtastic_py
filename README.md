# Basic script to store Meshtastic packet data to SQLITE3 db

This is just proof of concept.
Script uses default Serial connection. 

![](./images/screenshot.png)

Really basic setup :
```python
    # Initialize the serial interface
    interface = meshtastic.serial_interface.SerialInterface()

    # Subscribe to messages
    pub.subscribe(on_receive, "meshtastic.receive")
```

## Requirements

Requires `meshtastic` and `pytap2` and `sqlite3` modules.

```shell
pip3 install meshtastic
pip3 install pytap2
```

## Description

Basic setup of `SQLITE3` database for storing some data:

- Environment metrics (Temperature)
- Messages (Will keep track of all messages in default, and encrypted channels, also direct messages)
- Nodes (will try to make updated database of visible nodes)
- Positions (will keep track of all possitions packet recieved)
- Telemetry (basic telemetry received from nodes)
- Traceroute (WORK IN PROGRESS)

## Run 

```bash
python3 get-messages-to-db.py
```


## Query database

```bash
sqlite3 messages.db
```

### List tables

```shell
sqlite> .tables
environment  nodes        routing      traceroute 
messages     positions    telemetry 
```

### Sample Query to DB to list telemetry for specific node
```sql
-- SQLite
SELECT 
    nodes.short_name, 
    nodes.long_name, 
    telemetry.battery_level,
    telemetry.voltage, 
    telemetry.channel_utilization, 
    telemetry.air_util_tx,
    --telemetry.uptime_seconds,
    printf('%d days, %d hours, %d minutes', 
           telemetry.uptime_seconds / 86400, 
           (telemetry.uptime_seconds % 86400) / 3600, 
           (telemetry.uptime_seconds % 3600) / 60) AS uptime,
    datetime(telemetry.timestamp, 'unixepoch') AS datetime
FROM telemetry 
JOIN nodes ON telemetry.node_id = nodes.node_id
WHERE nodes.short_name = 'node1';


```