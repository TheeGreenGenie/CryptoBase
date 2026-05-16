from celery import shared_task


@shared_task(name="monitoring.sync_active_positions")
def sync_active_positions():
    return {"ok": True, "synced": 0}


@shared_task(name="monitoring.check_risk_alerts")
def check_risk_alerts():
    return {"ok": True, "alerts": 0}


@shared_task(name="monitoring.monitor_transaction_receipt")
def monitor_transaction_receipt(tx_hash: str):
    return {"ok": True, "tx_hash": tx_hash, "status": "pending"}


@shared_task(name="monitoring.evaluate_agent_suggestions")
def evaluate_agent_suggestions():
    return {"ok": True, "suggestions": 0}
