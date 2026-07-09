#!/bin/bash
cd /opt/fluidgo/app
docker compose -f docker-compose.prod.yml exec -T backend python smoke_test.py --base http://localhost
