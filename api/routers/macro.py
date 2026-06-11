"""Runic Macro Intelligence REST routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import optional_api_key
from api.services import reports_service as svc

router = APIRouter(prefix="/macro", tags=["macro"], dependencies=[Depends(optional_api_key)])


@router.get("/runic/nightly", operation_id="get_runic_nightly")
def get_runic_nightly() -> dict[str, Any]:
    try:
        return svc.load_runic_nightly()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/runic/variables/current", operation_id="get_runic_variables_current")
def get_runic_variables() -> dict[str, Any]:
    try:
        data = svc.load_runic_nightly()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {
        "date": data.get("date"),
        "regime": data.get("regime", {}),
        "variables_dashboard": data.get("variables_dashboard", []),
    }


@router.get("/combo/active", operation_id="get_active_combos")
def get_active_combos() -> dict[str, Any]:
    try:
        data = svc.load_runic_nightly()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {
        "date": data.get("date"),
        "dominant_signal": data.get("dominant_signal"),
        "active_combos": data.get("active_combos", []),
        "watch_combos": data.get("watch_combos", []),
    }


@router.get("/sentiment/positioning", operation_id="get_ssi_positioning")
def get_positioning() -> dict[str, Any]:
    try:
        return svc.load_positioning()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
