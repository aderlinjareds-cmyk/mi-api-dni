"""
API de consulta DNI via seeker.red
Desplegada en Railway
"""

import os
import httpx
import asyncio
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from typing import Optional

# ══════════════════════════════════════════
# ⚙️  CONFIGURACIÓN (variables de entorno)
# ══════════════════════════════════════════

SEEKER_TOKEN  = os.getenv("SEEKER_TOKEN", "")       # Tu token de seeker.red
API_KEY       = os.getenv("API_KEY", "")             # Clave para proteger TU api (opcional)
API_URL       = "https://seeker.red/personas/apiBasico/dni"
TIMEOUT       = 15

# ══════════════════════════════════════════
# 🚀 APP
# ══════════════════════════════════════════

app = FastAPI(
    title="Consultor DNI Perú",
    description="API para consultar DNI via seeker.red",
    version="1.0.0"
)


# ══════════════════════════════════════════
# 🔐 AUTENTICACIÓN OPCIONAL
# ══════════════════════════════════════════

async def verificar_api_key(x_api_key: Optional[str] = Header(None)):
    """Si API_KEY está configurada, valida el header X-Api-Key."""
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="API Key inválida o ausente")


# ══════════════════════════════════════════
# 🔍 ENDPOINTS
# ══════════════════════════════════════════

@app.get("/")
async def raiz():
    return {"status": "ok", "mensaje": "Consultor DNI corriendo en Railway 🚀"}


@app.get("/dni/{dni}", dependencies=[Depends(verificar_api_key)])
async def consultar_dni(dni: str):
    """Consulta un DNI individual."""

    if not dni.isdigit() or len(dni) != 8:
        raise HTTPException(status_code=400, detail="DNI debe tener exactamente 8 dígitos")

    if not SEEKER_TOKEN:
        raise HTTPException(status_code=500, detail="SEEKER_TOKEN no configurado en Railway")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {SEEKER_TOKEN}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"dni": dni},
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Error de seeker.red: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Error de conexión: {str(e)}")


@app.post("/dni/lote", dependencies=[Depends(verificar_api_key)])
async def consultar_lote(dnis: list[str]):
    """Consulta múltiples DNIs a la vez. Body: ["12345678", "87654321"]"""

    if len(dnis) > 20:
        raise HTTPException(status_code=400, detail="Máximo 20 DNIs por lote")

    invalidos = [d for d in dnis if not d.isdigit() or len(d) != 8]
    if invalidos:
        raise HTTPException(status_code=400, detail=f"DNIs inválidos: {invalidos}")

    semaforo = asyncio.Semaphore(5)

    async def consultar_uno(client, dni):
        async with semaforo:
            try:
                response = await client.post(
                    API_URL,
                    headers={
                        "Authorization": f"Bearer {SEEKER_TOKEN}",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data={"dni": dni},
                    timeout=TIMEOUT,
                )
                response.raise_for_status()
                return {"dni": dni, "status": "ok", "data": response.json()}
            except Exception as e:
                return {"dni": dni, "status": "error", "detalle": str(e)}

    async with httpx.AsyncClient() as client:
        tareas = [consultar_uno(client, dni) for dni in dnis]
        resultados = await asyncio.gather(*tareas)

    return {"total": len(resultados), "resultados": resultados}
