#!/usr/bin/env python3
"""setup_clickup_ot.py - Automates deployment of a complete Work Order workflow in a ClickUp Workspace.

Creates a Space named "Operaciones - OT Motores" with custom Statuses.
Within the Space it creates a Folder "Work Orders <year>".
Within the Folder it creates six Lists (Solicitudes, Sourcing, Cotizaciones,
Ordenes de Compra, Logistica, Entrega-Cierre).
Adds 10 key Custom Fields to each List.

Usage:
    export CLICKUP_API_TOKEN="pk_xxxxxxxxxxxxxxxxxxxxxxxx"
    python setup_clickup_ot.py --team TEAM_ID

Options:
    --team TEAM_ID       Numeric Workspace ID (required).
    --year YEAR          Year to include in Folder name (default: current year).
    --space-name NAME    Alternative Space name.
    -v, --verbose        Enable debug logging.

Notes:
    * Do not hard-code the token; use an environment variable or .env file.
    * Only ClickUp API v2 endpoints are used.
"""

import os
import sys
import time
import json
import argparse
import logging
from typing import Dict, List

import requests

API_ROOT = "https://api.clickup.com/api/v2"
TOKEN_ENV_VAR = "CLICKUP_API_TOKEN"

# ---------------------------------------------------------------------------
# Default configuration
# ---------------------------------------------------------------------------
DEFAULT_SPACE_NAME = "Operaciones - OT Motores"
DEFAULT_FOLDER_NAME = "Work Orders"
DEFAULT_LISTS = [
    "Solicitudes",        # phase 1
    "Sourcing",           # phases 3-4
    "Cotizaciones",       # phases 5-8
    "Ordenes de Compra",  # phase 9
    "Logistica",          # phase 10
    "Entrega-Cierre",     # phases 11-12
]

# Statuses must be unique within a Space
STATUSES = [
    {"status": "Draft", "color": "#9b9b9b", "type": "open", "orderindex": 0},
    {
        "status": "Ready for Sourcing",
        "color": "#f2c94c",
        "type": "in progress",
        "orderindex": 1,
    },
    {
        "status": "Quote Sent",
        "color": "#2d9cdb",
        "type": "in progress",
        "orderindex": 2,
    },
    {"status": "Accepted", "color": "#27ae60", "type": "complete", "orderindex": 3},
    {"status": "Lost", "color": "#eb5757", "type": "closed", "orderindex": 4},
    {"status": "Closed", "color": "#555555", "type": "closed", "orderindex": 5},
]

# Custom fields: type 3=number, 8=money, 5=date, 9=percent, 14=dropdown
CUSTOM_FIELDS = [
    {"name": "Valor FOB USD", "type": 8, "required": False, "type_config": {"default": "USD"}},
    {"name": "Valor DAP USD", "type": 8, "required": False, "type_config": {"default": "USD"}},
    {"name": "Margen %", "type": 9, "required": False},
    {"name": "Lead-time (días)", "type": 3, "required": False},
    {"name": "ETA Cliente", "type": 5, "required": False},
    {"name": "Proveedor", "type": 14, "required": False, "type_config": {"options": []}},
    {
        "name": "Incoterm",
        "type": 14,
        "required": False,
        "type_config": {"options": [{"name": "FOB"}, {"name": "DAP"}, {"name": "DDP"}]},
    },
    {"name": "Nº Parte OEM", "type": 3, "required": False},
    {"name": "Potencia kW", "type": 3, "required": False},
    {"name": "RPM Nominal", "type": 3, "required": False},
]

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def api_post(endpoint: str, payload: Dict, headers: Dict) -> Dict:
    """Wrapper for POST requests with basic error handling."""
    url = f"{API_ROOT}{endpoint}"
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code not in (200, 201):
        logging.error("POST %s -> %s: %s", endpoint, resp.status_code, resp.text)
        raise RuntimeError(f"API error {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def create_space(team_id: int, name: str, headers: Dict) -> str:
    payload = {
        "name": name,
        "multiple_assignees": True,
        "features": {"status": {"value": "custom"}},
        "statuses": STATUSES,
    }
    data = api_post(f"/team/{team_id}/space", payload, headers)
    space_id = data["id"]
    logging.info("Space '%s' creado (ID %s)", name, space_id)
    return space_id


def create_folder(space_id: str, name: str, year: int, headers: Dict) -> str:
    payload = {"name": f"{name} {year}"}
    data = api_post(f"/space/{space_id}/folder", payload, headers)
    folder_id = data["id"]
    logging.info("Folder '%s %s' creado (ID %s)", name, year, folder_id)
    return folder_id


def create_list(folder_id: str, name: str, headers: Dict) -> str:
    payload = {"name": name}
    data = api_post(f"/folder/{folder_id}/list", payload, headers)
    list_id = data["id"]
    logging.info("List '%s' creada (ID %s)", name, list_id)
    return list_id


def create_custom_fields(list_id: str, headers: Dict) -> None:
    for field in CUSTOM_FIELDS:
        api_post(f"/list/{list_id}/field", field, headers)
        logging.debug("  -> Field '%s' añadido a List %s", field["name"], list_id)
    logging.info("%d campos añadidos a List %s", len(CUSTOM_FIELDS), list_id)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Provisiona flujo OT en ClickUp automáticamente."
    )
    parser.add_argument(
        "--team", required=True, type=int, help="Team (Workspace) ID numérico"
    )
    parser.add_argument(
        "--year",
        default=time.strftime("%Y"),
        type=int,
        help="Año para el nombre del Folder (p.ej. 2025)",
    )
    parser.add_argument(
        "--space-name", default=DEFAULT_SPACE_NAME, help="Nombre del Space a crear"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Log a nivel DEBUG"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    token = os.getenv(TOKEN_ENV_VAR)
    if not token:
        sys.exit(
            f"ERROR: Variable de entorno {TOKEN_ENV_VAR} no encontrada. Exporta tu token primero."
        )

    headers = {"Authorization": token}

    try:
        space_id = create_space(args.team, args.space_name, headers)
        folder_id = create_folder(space_id, DEFAULT_FOLDER_NAME, args.year, headers)

        for lst in DEFAULT_LISTS:
            list_id = create_list(folder_id, lst, headers)
            create_custom_fields(list_id, headers)

        logging.info("\n✔ Flujo OT desplegado con éxito en ClickUp.")
    except Exception as exc:
        logging.error("Fallo en el despliegue: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
