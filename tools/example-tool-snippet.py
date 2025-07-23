# ==================== SYSTEM STATUS AND HEALTH ====================

@mcp.tool(tags={"rspace"})
def status() -> str:
    """
    System health check - determines if RSpace server is accessible and running
    
    Usage: Call this first to verify connectivity before other operations
    Returns: Status message from RSpace server
    """
    resp = eln_cli.get_status()
    return resp['message']