"""
Destination recommendation API endpoints.

Uses LLM to generate intelligent travel destination recommendations.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field
import time

from ....db.session import get_db
from ....core.auth import get_current_user, get_current_family
from ....core.llm import OpenAIAdapter
from ....config.settings import settings
from ..services.destination_recommender import DestinationRecommender


router = APIRouter(prefix="/trips", tags=["trip-destination"])


class DestinationRecommendationRequest(BaseModel):
    """Request schema for destination recommendation."""
    family_id: UUID
    occasion: Optional[str] = Field(None, description="Travel occasion (国庆, 春节, etc.)")
    budget_min: Optional[float] = Field(None, ge=0, description="Minimum budget")
    budget_max: Optional[float] = Field(None, ge=0, description="Maximum budget")
    duration_days: Optional[int] = Field(3, ge=1, le=30, description="Trip duration in days")
    season: Optional[str] = Field(None, description="Travel season")
    user_input: Optional[str] = Field(None, description="User's natural language request")


class DestinationRecommendationResponse(BaseModel):
    """Response schema for destination recommendations."""
    recommendations: List[dict]
    family_composition: dict
    generation_time_ms: int


@router.post("/recommend", response_model=DestinationRecommendationResponse)
async def get_destination_recommendations(
    request: DestinationRecommendationRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """
    Get intelligent destination recommendations.

    Analyzes family composition and generates personalized travel recommendations
    using LLM-based analysis.

    Request body:
    - family_id: Family identifier
    - occasion: Travel occasion (optional)
    - budget_min: Minimum budget (optional)
    - budget_max: Maximum budget (optional)
    - duration_days: Trip duration (default: 3)
    - season: Travel season (optional, auto-detected)
    - user_input: Natural language request (optional)

    Returns:
    - recommendations: List of 3 destination recommendations
    - family_composition: Family analysis result
    - generation_time_ms: Time taken to generate recommendations
    """
    try:
        start_time = time.time()

        # Initialize LLM adapter
        llm = OpenAIAdapter(settings.openai_api_key)

        # Initialize service (vector_db is optional, pass None)
        recommender = DestinationRecommender(db, llm, None)

        # Analyze family composition
        family_composition = await recommender.analyze_family_composition(
            family_id=request.family_id
        )

        # Generate recommendations
        recommendations = await recommender.generate_recommendations(
            family_composition=family_composition,
            occasion=request.occasion,
            budget_min=request.budget_min,
            budget_max=request.budget_max,
            duration_days=request.duration_days,
            season=request.season,
            user_input=request.user_input
        )

        generation_time = int((time.time() - start_time) * 1000)

        return {
            "recommendations": recommendations,
            "family_composition": family_composition,
            "generation_time_ms": generation_time
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate recommendations: {str(e)}")


@router.get("/destinations/search")
async def search_destinations(
    query: str,
    top_k: int = 5,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """
    Search destination knowledge base using semantic search.

    Query params:
    - query: Search query
    - top_k: Number of results (default: 5)

    Returns:
    - results: List of relevant destination information
    """
    try:
        # Initialize LLM adapter
        llm = OpenAIAdapter(settings.openai_api_key)

        # Initialize service (vector_db is None for now)
        recommender = DestinationRecommender(db, llm, None)

        results = await recommender.search_destination_knowledge(
            query=query,
            top_k=top_k
        )

        return {
            "query": query,
            "results": results,
            "count": len(results)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
