#!/bin/bash
set -e
echo "Rodando migrations..."
cd backend
alembic upgrade head
echo "Migrations concluídas."
