#!/bin/bash
pg_dump -h localhost -U radar radar --inserts -t modelagem_* -f $RADAR_HOME/static/db-dump/radar.sql