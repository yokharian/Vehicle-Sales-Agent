"""
Tests for the combined agent workflow: catalog search plus document search.
"""

import sys
from pathlib import Path

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding


sys.path.append(str(Path(__file__).parent.parent / "src"))

from db.document_loader import ensure_tables, reindex
from tools.catalog_search import catalog_search_tool
from tools.document_search import document_search_tool
from tools.financing_calculator import financing_calculator_tool


FAKE_EMBEDDINGS = DeterministicFakeEmbedding(size=768)

DOCUMENT_SEED = [
    Document(
        page_content=(
            "Kavak ofrece vehículos seminuevos certificados con garantía mecánica, "
            "entrega a domicilio y financiamiento a tasa fija."
        ),
        metadata={"source": "kavak.md", "chunk_index": 0},
    ),
    Document(
        page_content=(
            "Para comprar en Kavak se requiere identificación oficial vigente, "
            "comprobante de domicilio y comprobantes de ingresos."
        ),
        metadata={"source": "kavak.md", "chunk_index": 1},
    ),
]


@pytest.fixture
def document_index():
    ensure_tables()
    reindex(DOCUMENT_SEED, FAKE_EMBEDDINGS)
    yield FAKE_EMBEDDINGS


@pytest.mark.usefixtures("document_index")
def test_find_vehicle_then_retrieve_company_evidence():
    """Catalog finds a vehicle; document search returns company evidence."""
    _, vehicles = catalog_search_tool.func(make="toyota", max_results=2)

    assert vehicles
    assert all(vehicle.make == "toyota" for vehicle in vehicles)

    _, evidence = document_search_tool.func(query="¿Qué ofrece Kavak?", k=2)

    assert evidence
    assert all(result.metadata.source == "kavak.md" for result in evidence)


@pytest.mark.usefixtures("document_index")
def test_vehicle_price_feeds_financing_and_documents_backs_company_facts():
    """A catalog result drives the financing calculator; document grounds claims."""
    _, vehicles = catalog_search_tool.func(make="honda", max_results=1)

    assert vehicles
    vehicle = vehicles[0]

    _, financing = financing_calculator_tool.func(
        vehicle_price=vehicle.price,
        down_payment=0.0,
        term_years=5,
    )
    assert financing.financed_amount == vehicle.price
    assert financing.monthly_payment > 0

    _, evidence = document_search_tool.func(query="requisitos para comprar", k=1)
    assert evidence
    assert evidence[0].metadata.source == "kavak.md"


def test_agent_toolbelt_exposes_catalog_and_documents():
    """Both tools are registered with distinct names and valid schemas."""
    tools = {
        catalog_search_tool.name: catalog_search_tool,
        document_search_tool.name: document_search_tool,
    }

    assert set(tools) == {"catalog_search", "document_search"}
    for tool in tools.values():
        assert callable(tool.func)
        assert tool.args_schema is not None
