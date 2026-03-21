import logging
from datetime import datetime, timezone, timedelta
from typing import List

from app.db.firestore_wrapper import get_db
from app.models.user import AgentPerformance
from app.models.message import ServiceMetrics


db = get_db()


class MetricsService:
    """Serviço para cálculo de métricas de atendimento"""

    @staticmethod
    async def get_agents_performance() -> List[AgentPerformance]:
        """Get performance metrics for all agents"""
        if db is None:
            return []

        try:
            agents = await db.users.find({"role": "agent"}).to_list(1000)
            performance_list = []

            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

            for agent in agents:
                if not agent:
                    continue

                agent_id = agent.get("id") or agent.get("username")
                if not agent_id:
                    continue

                # Isolamos as consultas para evitar que falhas em uma zerem os dados das outras
                total_conversations = 0
                try:
                    total_conversations = await db.clients.count_documents({"assigned_agent": agent_id})
                except Exception as e:
                    logging.error(f"Erro ao contar total de conversas do agente {agent_id}: {e}")

                conversations_today = 0
                try:
                    conversations_today = await db.clients.count_documents({
                        "assigned_agent": agent_id,
                        "status": "finished",
                        "service_finished_at": {"$gte": today_start}
                    })
                except Exception as e:
                    logging.error(f"Erro ao contar conversas de hoje do agente {agent_id}: {e}")

                finished_conversations = []
                try:
                    finished_conversations = await db.clients.find({
                        "assigned_agent": agent_id,
                        "status": "finished"
                    }).to_list(1000)
                except Exception as e:
                    logging.error(f"Erro ao buscar conversas finalizadas do agente {agent_id}: {e}")

                total_duration = 0
                count = 0
                for conv in finished_conversations:
                    start = conv.get("service_started_at")
                    end = conv.get("service_finished_at")
                    if isinstance(start, datetime) and isinstance(end, datetime):
                        duration = (end - start).total_seconds() / 60  # minutes
                        total_duration += duration
                        count += 1

                avg_response_time = total_duration / count if count > 0 else 0

                # Converte de decimal para formato de relógio "MM:SS"
                minutes = int(avg_response_time)
                seconds = int((avg_response_time - minutes) * 60)
                avg_time_formatted = f"{minutes:02d}:{seconds:02d}"

                performance = AgentPerformance(
                    agent_id=str(agent_id),
                    agent_name=str(agent.get("full_name") or agent.get("username") or "Agente Desconhecido"),
                    total_conversations=total_conversations,
                    avg_response_time_minutes=avg_time_formatted,
                    conversations_finished_today=conversations_today,
                    status=str(agent.get("status", "offline")),
                    last_activity=agent.get("last_activity") or agent.get("created_at") or datetime.now(timezone.utc)
                )
                performance_list.append(performance)

            return performance_list
        except Exception as e:
            logging.error(f"Erro crítico em get_agents_performance: {e}", exc_info=True)
            return []

    @staticmethod
    async def get_service_metrics() -> List[ServiceMetrics]:
        """Get detailed service metrics"""
        if db is None:
            return []

        try:
            thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

            try:
                finished_conversations = await db.clients.find({
                    "status": "finished",
                    "service_finished_at": {"$gte": thirty_days_ago}
                }).to_list(1000)
            except Exception as e:
                logging.error(f"Erro ao buscar métricas de serviço no Firestore: {e}")
                return []

            metrics_list = []
            for conv in finished_conversations:
                agent_id = conv.get("assigned_agent")
                if not agent_id:
                    continue

                agent_name = "Agente Desconhecido"
                try:
                    agent = await db.users.find_one({"id": agent_id})
                    if agent:
                        agent_name = str(agent.get("full_name") or agent.get("username") or "Agente Desconhecido")
                except Exception as e:
                    logging.error(f"Erro ao buscar nome do agente {agent_id}: {e}")

                duration = None
                start = conv.get("service_started_at")
                end = conv.get("service_finished_at")

                if isinstance(start, datetime) and isinstance(end, datetime):
                    duration = (end - start).total_seconds() / 60

                metric = ServiceMetrics(
                    conversation_id=str(conv.get("id") or "unknown"),
                    client_phone=str(conv.get("phone_number") or conv.get("id") or "unknown"),
                    client_name=conv.get("name"),
                    agent_id=str(agent_id),
                    agent_name=agent_name,
                    service_duration_minutes=round(duration, 2) if duration else None,
                    started_at=start if isinstance(start, datetime) else (conv.get("created_at") if isinstance(conv.get("created_at"), datetime) else datetime.now(timezone.utc)),
                    finished_at=end if isinstance(end, datetime) else None
                )
                metrics_list.append(metric)

            return sorted(metrics_list, key=lambda x: x.finished_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        except Exception as e:
            logging.error(f"Erro crítico em get_service_metrics: {e}", exc_info=True)
            return []
