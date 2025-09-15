from typing import Any

from fastapi import APIRouter, Query, Depends, HTTPException, status
from fastapi_filter import FilterDepends
from sqlalchemy.ext.asyncio import AsyncSession

import app.deps as deps
import app.crud as crud, app.models as models, app.schemas as schemas


router = APIRouter()
