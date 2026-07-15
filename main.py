"""
RSpace MCP Server

This MCP server provides access to RSpace's Electronic Lab Notebook (ELN) and 
Inventory Management systems through a set of tools.

Architecture:
- Uses FastMCP framework for tool registration and server setup
- Connects to RSpace via official Python client libraries (rspace_client)
- Uses Pydantic models for type safety and validation

Extension Guide:
- ELN tools: Add new functions using @mcp.tool decorator with tags={"rspace"}
- Inventory tools: Use tags={"rspace", "inventory", "<category>"} for organization
- Follow existing patterns for error handling and return types
- All tools should include comprehensive docstrings for Claude's understanding
"""

from typing import Annotated, Any, Dict, List, Optional, Union, Literal

from fastmcp import FastMCP
from rspace_client.eln import eln as e  # Electronic Lab Notebook client
from rspace_client.inv import inv as i  # Inventory Management client
from rspace_client.eln.advanced_query_builder import AdvancedQueryBuilder
import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# ============================================================================
# PYDANTIC MODELS - Data Structure Definitions
# ============================================================================
# These models define the structure of data returned by RSpace APIs
# Extend these when adding new data types or modify existing ones for new fields

class Document(BaseModel):
    """ELN Document metadata - used for document listings"""
    name: str = Field(description="Document name")
    globalId: str = Field(description="Global identifier")
    created: str = Field(description="The document's creation date")


class RSField(BaseModel):
    """Individual field content within an ELN document"""
    textContent: str = Field(description="text content of a field as HTML")


class FullDocument(BaseModel):
    """Complete ELN document with all content concatenated"""
    content: str = Field(description="concatenated text content from all fields")


class Sample(BaseModel):
    """Inventory sample metadata"""
    name: str = Field(description="Sample name")
    globalId: str = Field(description="Global identifier")
    created: str = Field(description="Creation date")
    tags: List[str] = Field(default_factory=list, description="Sample tags")
    quantity: Optional[Dict] = Field(default=None, description="Sample quantity and units")


class Container(BaseModel):
    """Inventory container metadata"""
    name: str = Field(description="Container name")
    globalId: str = Field(description="Global identifier")
    cType: str = Field(description="Container type (LIST, GRID, WORKBENCH, IMAGE)")
    capacity: Optional[int] = Field(default=None, description="Container capacity if applicable")


class GridLocation(BaseModel):
    """Specific position within a grid container"""
    x: int = Field(description="Column position (1-based)")
    y: int = Field(description="Row position (1-based)")


# ============================================================================
# SERVER INITIALIZATION AND CLIENT SETUP
# ============================================================================
# This section handles MCP server setup and RSpace client authentication
# Modify environment variable names here if your deployment uses different names

mcp = FastMCP("RSpace MCP Server")
load_dotenv()

# Environment configuration - customize these variable names as needed
api_key = os.getenv("RSPACE_API_KEY")
api_url = os.getenv("RSPACE_URL")

if not api_key or not api_url:
    raise RuntimeError(
        "RSpace MCP server cannot start: RSPACE_API_KEY and RSPACE_URL must both "
        "be set in the environment (e.g. via a .env file in the working directory)."
    )

# Initialize RSpace clients
eln_cli = e.ELNClient(api_url, api_key)  # Electronic Lab Notebook operations
inv_cli = i.InventoryClient(api_url, api_key)  # Inventory Management operations


def _bulk_result(result) -> dict:
    """Normalise an SDK BulkOperationResult into a JSON-friendly shape."""
    if isinstance(result, i.BulkOperationResult):
        successes = list(result.success_results() or [])
        errors = list(result.error_results() or [])
        return {
            "success": result.is_ok(),
            "success_count": len(successes),
            "error_count": len(errors),
            "results": list(result.results() or []),
            "errors": errors,
        }
    return {"success": True, "results": result}


# ============================================================================
# ELECTRONIC LAB NOTEBOOK (ELN) TOOLS
# ============================================================================
# This section contains all tools related to documents, notebooks, forms, and
# general ELN functionality. When adding new ELN features, add them here.

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


# ==================== DOCUMENT MANAGEMENT ====================
# Core document operations - reading, creating, updating documents

@mcp.tool(tags={"rspace"})
def get_documents(query: str = None, page_size: int = 20, page_number: int = 0) -> list[Document]:
    """
    Retrieves RSpace documents with pagination, optionally filtered by a search term

    Usage: Get an overview of documents for browsing/selection, or narrow the list
      with a search term.
    query: Optional free-text search term, behaving like RSpace's simple "All"
      search (matches name, content, tags, and global ID). For example,
      query="SD59540" returns just that document. Omit it to list recent documents.
    Note: To fetch a single document's full content by ID, use
      get_single_Rspace_document, which looks up an exact numeric or global ID.
    Limit: Maximum 200 documents per call for performance
    Pagination: page_number is 0-based; combine with page_size to walk results
    Returns: List of document metadata (not full content)
    """
    if page_size > 200 or page_size < 0:
        raise ValueError("page_size must be between 0 and 200")
    if page_number < 0:
        raise ValueError("page_number must be >= 0")
    resp = eln_cli.get_documents(query=query, page_size=page_size, page_number=page_number)
    return resp['documents']


@mcp.tool(tags={"rspace"}, name="get_single_Rspace_document")
def get_document(doc_id: int | str) -> FullDocument:
    """
    Retrieves complete content of a single document
    
    Usage: Get full document text for reading/analysis
    Parameters: doc_id can be numeric ID or string globalId (e.g., "SD12345")
    Returns: Full document with concatenated field content
    """
    resp = eln_cli.get_document(doc_id)
    # Concatenate all field content for easier processing
    resp['content'] = ''
    for fld in resp['fields']:
        resp['content'] = resp['content'] + fld['content']
    return resp


@mcp.tool(tags={"rspace"})
def update_document(
    document_id: int | str,
    name: str = None,
    tags: List[str] = None,
    form_id: int | str | None = None,
    fields: List[dict] = None
) -> dict:
    """
    Updates existing RSpace document content and metadata
    
    Usage: Modify document name, tags, or field content
    Fields format: [{"id": field_id, "content": "new HTML content"}]
    Returns: Updated document information
    """
    return eln_cli.update_document(
        document_id=document_id,
        name=name,
        tags=tags,
        form_id=form_id,
        fields=fields
    )


@mcp.tool(tags={"rspace", "search"})
def search_documents(
    query: str,
    search_type: Literal["simple", "advanced"] = "simple",
    query_types: List[Literal["global", "fullText", "tag", "name", "created", "lastModified", "form", "attachment"]] = None,
    operator: Literal["and", "or"] = "and",
    order_by: str = "lastModified desc",
    page_number: int = 0,
    page_size: int = 20,
    include_content: bool = False
) -> dict:
    """
    Generic search tool for RSpace documents with flexible search options
    
    Usage: Search across all your RSpace documents using various criteria
    
    Parameters:
    - query: The search term(s) to look for
    - search_type: "simple" for basic search, "advanced" for multi-criteria search
    - query_types: List of search types to use (for advanced search):
        - "global": Search across all document content and metadata
        - "fullText": Search within document text content
        - "tag": Search by document tags
        - "name": Search by document names/titles
        - "created": Search by creation date (use ISO format like "2024-01-01")
        - "lastModified": Search by modification date
        - "form": Search by form type
        - "attachment": Search by attachments
    - operator: "and" (all criteria must match) or "or" (any criteria can match)
    - order_by: Sort results by field (e.g., "lastModified desc", "name asc")
    - page_number: Page number for pagination (0-based)
    - page_size: Number of results per page (max 200)
    - include_content: Whether to fetch full document content (slower but more complete)
    
    Returns: Dictionary with search results and metadata
    
    Examples:
    - Simple text search: search_documents("PCR protocol")
    - Search by tags: search_documents("experiment", search_type="advanced", query_types=["tag"])
    - Multi-criteria search: search_documents("DNA", search_type="advanced", 
                                            query_types=["fullText", "tag"], operator="or")
    """
    if page_size > 200:
        raise ValueError("page_size must be 200 or less")
    # include_content fetches each matched document one-by-one (N+1 HTTP calls).
    # Cap it to a reasonable batch so a careless call can't fan out to 200 fetches.
    if include_content and page_size > 25:
        raise ValueError(
            "include_content=True is limited to page_size <= 25 because each "
            "result triggers an extra fetch. Lower page_size or paginate."
        )

    if search_type == "simple":
        # Use simple search - works like RSpace's "All" search
        results = eln_cli.get_documents(
            query=query,
            order_by=order_by,
            page_number=page_number,
            page_size=page_size
        )
    else:
        # Use advanced search with AdvancedQueryBuilder
        if query_types is None:
            query_types = ["global"]  # Default to global search
        
        builder = AdvancedQueryBuilder(operator=operator)
        
        # Add search terms for each specified query type
        for query_type in query_types:
            if query_type == "global":
                builder.add_term(query, AdvancedQueryBuilder.QueryType.GLOBAL)
            elif query_type == "fullText":
                builder.add_term(query, AdvancedQueryBuilder.QueryType.FULL_TEXT)
            elif query_type == "tag":
                builder.add_term(query, AdvancedQueryBuilder.QueryType.TAG)
            elif query_type == "name":
                builder.add_term(query, AdvancedQueryBuilder.QueryType.NAME)
            elif query_type == "created":
                builder.add_term(query, AdvancedQueryBuilder.QueryType.CREATED)
            elif query_type == "lastModified":
                builder.add_term(query, AdvancedQueryBuilder.QueryType.LAST_MODIFIED)
            elif query_type == "form":
                builder.add_term(query, AdvancedQueryBuilder.QueryType.FORM)
            elif query_type == "attachment":
                builder.add_term(query, AdvancedQueryBuilder.QueryType.ATTACHMENT)
        
        advanced_query = builder.get_advanced_query()
        results = eln_cli.get_documents_advanced_query(
            advanced_query=advanced_query,
            order_by=order_by,
            page_number=page_number,
            page_size=page_size
        )
    
    # Optionally fetch full content for each document
    if include_content and 'documents' in results:
        for doc in results['documents']:
            try:
                full_doc = eln_cli.get_document(doc['globalId'])
                # Add concatenated content to the document
                content = ''
                for field in full_doc.get('fields', []):
                    content += field.get('content', '')
                doc['fullContent'] = content
            except Exception as e:
                doc['fullContent'] = f"Error fetching content: {str(e)}"
    
    return results


@mcp.tool(tags={"rspace", "search"})
def search_by_tags(
    tags: List[str],
    operator: Literal["and", "or"] = "and",
    order_by: str = "lastModified desc", 
    page_number: int = 0,
    page_size: int = 20
) -> dict:
    """
    Search documents by specific tags
    
    Usage: Find documents tagged with specific keywords
    
    Parameters:
    - tags: List of tags to search for
    - operator: "and" (document must have all tags) or "or" (document can have any tag)
    - order_by: Sort results by field
    - page_number: Page number for pagination
    - page_size: Number of results per page
    
    Returns: Dictionary with search results
    
    Example: search_by_tags(["PCR", "protocol"], operator="and")
    """
    builder = AdvancedQueryBuilder(operator=operator)
    
    for tag in tags:
        builder.add_term(tag, AdvancedQueryBuilder.QueryType.TAG)
    
    advanced_query = builder.get_advanced_query()
    return eln_cli.get_documents_advanced_query(
        advanced_query=advanced_query,
        order_by=order_by,
        page_number=page_number,
        page_size=page_size
    )


@mcp.tool(tags={"rspace", "search"})
def search_recent_documents(
    days_back: int = 7,
    query: str = None,
    page_size: int = 20
) -> dict:
    """
    Search for recently modified documents
    
    Usage: Find documents modified within a specific timeframe
    
    Parameters:
    - days_back: Number of days to look back
    - query: Optional text search within recent documents
    - page_size: Number of results to return
    
    Returns: Dictionary with recent documents
    
    Example: search_recent_documents(7, "experiment")
    """
    from datetime import datetime, timedelta
    
    # Calculate date range - RSpace expects "startDate;endDate" format for date ranges
    start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    date_range = f"{start_date};{end_date}"
    
    builder = AdvancedQueryBuilder(operator="and")
    builder.add_term(date_range, AdvancedQueryBuilder.QueryType.LAST_MODIFIED)
    
    if query:
        builder.add_term(query, AdvancedQueryBuilder.QueryType.GLOBAL)
    
    advanced_query = builder.get_advanced_query()
    return eln_cli.get_documents_advanced_query(
        advanced_query=advanced_query,
        order_by="lastModified desc",
        page_number=0,
        page_size=page_size
    )


@mcp.tool(tags={"rspace", "search"})
def find_documents_by_content(
    content_terms: List[str],
    operator: Literal["and", "or"] = "and",
    order_by: str = "lastModified desc",
    page_size: int = 20
) -> dict:
    """
    Full-text content-based document search

    Usage: Find documents containing specific content terms

    Parameters:
    - content_terms: List of terms that should appear in document content
    - operator: "and" (all terms must appear) or "or" (any term can appear)
    - order_by: Sort results by field
    - page_size: Number of results to return

    Returns: Dictionary with search results

    Example: find_documents_by_content(["DNA", "extraction"], operator="and")
    """
    builder = AdvancedQueryBuilder(operator=operator)

    for term in content_terms:
        builder.add_term(term, AdvancedQueryBuilder.QueryType.FULL_TEXT)

    advanced_query = builder.get_advanced_query()
    return eln_cli.get_documents_advanced_query(
        advanced_query=advanced_query,
        order_by=order_by,
        page_number=0,
        page_size=page_size
    )

# ==================== NOTEBOOK OPERATIONS ====================
# Specialized tools for notebook creation and entry management

@mcp.tool(tags={"rspace"}, name="createNewNotebook")
def create_notebook(
        name: Annotated[str, Field(description="The name of the notebook to create")],
) -> Dict[str, any]:
    """
    Creates a new electronic lab notebook
    
    Usage: Organize related experiments/entries under a single notebook
    Returns: Created notebook information including ID for adding entries
    """
    resp = eln_cli.create_folder(name, notebook=True)
    return resp


@mcp.tool(tags={"rspace"}, name="createNotebookEntry")
def create_notebook_entry(
        name: Annotated[str, Field(description="The name of the notebook entry")],
        text_content: Annotated[str, Field(description="html or plain text content ")],
        notebook_id: Annotated[int, Field(description="The id of the notebook to add the entry")],
) -> Dict[str, any]:
    """
    Adds a new entry to an existing notebook
    
    Usage: Add experimental procedures, results, or observations to a notebook
    Content: Supports both HTML and plain text formatting
    Returns: Created entry information
    """
    resp = eln_cli.create_document(name, parent_folder_id=notebook_id, fields=[{'content': text_content}])
    return resp


# ==================== DOCUMENT METADATA MANAGEMENT ====================
# Tools for organizing and categorizing documents

def _current_doc_tags(doc_id: Union[int, str]) -> List[str]:
    """Fetch a document's tags as a deduplicated list (server returns CSV string)."""
    doc = eln_cli.get_document(doc_id)
    raw = doc.get("tags") or ""
    if isinstance(raw, list):
        items = raw
    else:
        items = raw.split(",")
    seen, out = set(), []
    for t in items:
        t = t.strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


@mcp.tool(tags={"rspace"}, name="tagDocumentOrNotebookEntry")
def tag_document(
        doc_id: int | str,
        tags: Annotated[List[str], Field(description="One or more tags to add")]
) -> Dict[str, any]:
    """
    Appends tags to a document, preserving any tags already set

    Usage: Categorize documents by project, experiment type, etc.
    Behaviour: Existing tags are kept; duplicates are deduplicated
    To replace or remove tags, use update_document or remove_tags_from_document.
    Returns: Updated document with the merged tag set
    """
    existing = _current_doc_tags(doc_id)
    seen = {t.lower() for t in existing}
    merged = existing + [t.strip() for t in tags if t.strip() and t.strip().lower() not in seen]
    return eln_cli.update_document(document_id=doc_id, tags=merged)


@mcp.tool(tags={"rspace"})
def remove_tags_from_document(
        doc_id: int | str,
        tags: Annotated[List[str], Field(description="One or more tags to remove (case-insensitive)")]
) -> Dict[str, any]:
    """
    Removes specific tags from a document, leaving other tags intact

    Usage: Untag documents without overwriting the rest of their tag set
    Matching: Case-insensitive
    Returns: Updated document with the requested tags removed
    """
    existing = _current_doc_tags(doc_id)
    drop = {t.strip().lower() for t in tags if t.strip()}
    remaining = [t for t in existing if t.lower() not in drop]
    return eln_cli.update_document(document_id=doc_id, tags=remaining)


@mcp.tool(tags={"rspace"}, name="renameDocumentOrNotebookEntry")
def rename_document(
        doc_id: int | str,
        name: str
) -> Dict[str, any]:
    """
    Changes the name/title of a document or notebook entry
    
    Usage: Update document titles for better organization
    Returns: Updated document information
    """
    resp = eln_cli.update_document(document_id=doc_id, name=name)
    return resp


# ==================== FORM MANAGEMENT ====================
# Custom form creation and management for structured data entry

@mcp.tool(tags={"rspace"})
def get_forms(query: str = None, order_by: str = "lastModified desc", page_number: int = 0, page_size: int = 20) -> dict:
    """
    Lists available custom forms for structured document creation
    
    Usage: Browse available templates before creating structured documents
    Filtering: Use query parameter to search form names/descriptions
    Returns: Paginated list of form metadata
    """
    return eln_cli.get_forms(query=query, order_by=order_by, page_number=page_number, page_size=page_size)


@mcp.tool(tags={"rspace"})
def get_form(form_id: int | str) -> dict:
    """
    Retrieves detailed information about a specific form template
    
    Usage: Examine form structure before creating documents or new forms
    Returns: Complete form definition including field specifications
    """
    return eln_cli.get_form(form_id)


@mcp.tool(tags={"rspace"})
def create_form(
    name: str,
    tags: List[str] = None,
    fields: List[dict] = None
) -> dict:
    """
    Creates a new custom form template for structured data entry
    
    Usage: Define reusable templates for experiments, protocols, reports
    Fields structure:
    [
        {
            "name": "Field Name",
            "type": "String|Text|Number|Radio|Date|Choice",
            "mandatory": True/False,
            "defaultValue": "optional default"
        }
    ]
    Field types are capitalised here (String, Text, Number, Radio, Date, Choice),
    unlike instrument/sample templates which use lowercase type names.

    Radio and Choice fields REQUIRE a flat "options" list on the field, e.g.
        {"name": "Imaging Mode", "type": "Radio", "mandatory": False,
         "options": ["Bright Field", "Dark Field", "HAADF-STEM"]}
    Note this differs from create_instrument_template, whose radio/choice options
    are nested under "definition": {"options": [...]}. Omitting "options" on a
    Radio/Choice field fails with "Please provide at least one option".
    Returns: Created form information (form will be in NEW state)
    """
    return eln_cli.create_form(name=name, tags=tags, fields=fields)


@mcp.tool(tags={"rspace"})
def publish_form(form_id: int | str) -> dict:
    """
    Makes a form available for creating documents
    
    Usage: Activate form after creation/modification
    Note: Forms must be published before they can be used for document creation
    Returns: Updated form status
    """
    return eln_cli.publish_form(form_id)


@mcp.tool(tags={"rspace"})
def unpublish_form(form_id: int | str) -> dict:
    """
    Hides a form from document creation interface
    
    Usage: Temporarily disable forms without deletion
    Returns: Updated form status
    """
    return eln_cli.unpublish_form(form_id)


@mcp.tool(tags={"rspace"})
def share_form(form_id: int | str) -> dict:
    """
    Shares form with user's groups for collaborative use
    
    Usage: Make custom forms available to team members
    Returns: Updated sharing status
    """
    return eln_cli.share_form(form_id)


@mcp.tool(tags={"rspace"})
def unshare_form(form_id: int | str) -> dict:
    """
    Removes form sharing with groups
    
    Usage: Make form private again
    Returns: Updated sharing status
    """
    return eln_cli.unshare_form(form_id)


@mcp.tool(tags={"rspace"})
def delete_form(form_id: int | str) -> dict:
    """
    Permanently deletes a form template
    
    Usage: Remove unused forms (only works for forms in NEW state)
    Warning: This operation cannot be undone
    Returns: Deletion confirmation
    """
    return eln_cli.delete_form(form_id)


@mcp.tool(tags={"rspace"})
def create_document_from_form(
    form_id: int | str,
    name: str = None,
    parent_folder_id: int | str | None = None,
    tags: List[str] = None,
    fields: List[dict] = None
) -> dict:
    """
    Creates a structured document using a form template
    
    Usage: Generate documents with predefined structure and validation
    Fields: Pre-populate form fields with initial data
    Returns: Created document information
    """
    return eln_cli.create_document(
        name=name,
        parent_folder_id=parent_folder_id,
        tags=tags,
        form_id=form_id,
        fields=fields
    )


# ==================== AUDIT AND ACTIVITY TRACKING ====================
# Tools for monitoring system usage and document history

@mcp.tool(tags={"rspace"}, name="getAuditEvents")
def activity(
        username: str = None,
        global_id: str = None,
        date_from: str = None,
        date_to: str = None
) -> Dict[str, any]:
    """
    Retrieves audit trail of all actions performed in RSpace
    
    Usage: Monitor document access, modifications, and user activity
    Filtering options:
    - username: Filter by specific user actions
    - global_id: Filter by specific document
    - date_from/date_to: ISO8601 format date range
    
    Returns: Chronological list of system events
    """
    users = [username] if username else None
    resp = eln_cli.get_activity(users=users, global_id=global_id, date_from=date_from, date_to=date_to)
    return resp


# ==================== FILE MANAGEMENT ====================
# Tools for handling file attachments and downloads

@mcp.tool(tags={"rspace"}, name="downloadFile")
def download_file(
        file_id: int,
        file_path: str
) -> Dict[str, any]:
    """
    Downloads file attachments from RSpace documents
    
    Usage: Retrieve images, data files, or other attachments
    Parameters:
    - file_id: Numeric ID of the file attachment
    - file_path: Local filesystem path where file should be saved
    
    Returns: Download status and file information
    """
    # 64 KB chunks — large enough to keep TCP throughput up, small enough that
    # we don't hold a giant file in memory if the SDK does that internally.
    resp = eln_cli.download_file(file_id=file_id, filename=file_path, chunk_size=64 * 1024)
    return resp

@mcp.tool(tags={"rspace", "files"})
def uploadAndAttachFile(
    document_id: Union[int, str],
    file_path: str,
    caption: Optional[str] = None,
    heading: Optional[str] = None,
    field_id: Optional[Union[int, str]] = None,
) -> dict:
    """
    Uploads a file to RSpace and attaches it to a document as a proper file attachment

    Usage: One-step process to upload any file and attach it to an RSpace document
    File types: Supports all file types (images, PDFs, data files, protocols, etc.)
    Attachment: Creates proper RSpace file attachment, not just a link

    Parameters:
    - document_id: RSpace document ID (numeric or global ID like "SD12345")
    - file_path: Path to the file to upload (e.g., "data/results.pdf")
    - caption: Optional caption stored as the file's gallery metadata (visible in
      the file properties view)
    - heading: Optional bold heading inserted in the document above the attachment
    - field_id: Numeric ID of the document field to append the attachment to.
      Defaults to the first field. Use get_single_Rspace_document to discover
      field IDs for multi-field forms.

    Returns: Upload confirmation and document update information
    """
    try:
        # Step 1: Upload the file to RSpace (caption -> file gallery metadata)
        with open(file_path, 'rb') as file:
            upload_result = eln_cli.upload_file(file, caption=caption)
        
        file_id = upload_result.get('id')
        if not file_id:
            return {"error": "File upload failed - no file ID returned"}
        
        # Step 2: Get the current document
        document = eln_cli.get_document(document_id)
        if not document.get('fields'):
            return {"error": f"Document {document_id} has no fields to attach file to"}
        
        # Step 3: Create proper RSpace file attachment
        # This is the key fix - use RSpace's native attachment format
        attachment_html = f'<fileId={file_id}>'
        
        # Add heading as a separate paragraph if provided
        if heading:
            attachment_html = f'<p><strong>{heading}</strong></p>\n{attachment_html}'
        
        # Step 4: Update the document with the file attachment
        if field_id is not None:
            target = next(
                (f for f in document['fields'] if str(f['id']) == str(field_id)),
                None,
            )
            if target is None:
                return {"error": f"Document {document_id} has no field with id {field_id}"}
        else:
            target = document['fields'][0]
        current_content = target.get('content', '')
        updated_content = current_content + '\n' + attachment_html

        # Update the document
        update_result = eln_cli.update_document(
            document_id=document_id,
            fields=[{
                'id': target['id'],
                'content': updated_content
            }]
        )
        
        return {
            "success": True,
            "message": "File uploaded and attached successfully",
            "file_info": {
                "file_id": file_id,
                "name": upload_result.get('name'),
                "size": upload_result.get('size'),
                "globalId": upload_result.get('globalId'),
                "caption": caption
            },
            "attachment_info": {
                "document_id": str(document_id),
                "heading": heading,
                "attachment_format": "rspace_native",
                "field_updated": target['id']
            },
            "updated_document": update_result
        }
        
    except FileNotFoundError:
        return {"error": f"File not found: {file_path}"}
    except Exception as e:
        return {"error": f"Failed to upload and attach file: {str(e)}"}

# ============================================================================
# INVENTORY MANAGEMENT TOOLS
# ============================================================================
# This section contains all tools related to sample management, container
# organization, and inventory tracking. When adding new inventory features,
# organize them by category (samples, containers, movement, templates, utility).

# ==================== SAMPLE MANAGEMENT ====================
# Core sample creation, retrieval, and manipulation tools

def _normalise_inventory_tags(tags: List[Any]) -> List[dict]:
    """Wrap plain-string tags into the ApiTagInfo dict shape the inventory API
    requires. Dicts (already {"value": ...}) are passed through unchanged, so a
    mix of strings and dicts is tolerated. Mirrors i.gen_tags for the string case.
    """
    normalised = []
    for tag in tags:
        if isinstance(tag, str):
            normalised.append({
                "value": tag,
                "ontologyName": None,
                "ontologyVersion": None,
                "uri": None,
            })
        else:
            normalised.append(tag)
    return normalised


def _resolve_quantity_unit(label: str) -> dict:
    """Look up a quantity unit definition, tolerant of casing.

    The client's QuantityUnit.of does an exact, case-sensitive match, so common
    abbreviations like "L" or "mL" are rejected even though "l"/"ml" exist. We
    try the exact match first (so uppercase-only units C/K/F still resolve),
    then fall back to a case-insensitive match before giving up with a message
    that lists the accepted units.
    """
    from rspace_client.inv import quantity_unit as qu
    if qu.QuantityUnit.is_supported_unit(label):
        return qu.QuantityUnit.of(label)
    lowered = label.lower()
    for candidate in qu.QuantityUnit.unit_labels():
        if candidate.lower() == lowered:
            return qu.QuantityUnit.of(candidate)
    raise ValueError(
        f"'{label}' is not a recognised unit. Valid units: "
        f"{', '.join(qu.QuantityUnit.unit_labels())}."
    )


def _unit_dimension(unit_id: Any) -> Optional[str]:
    """Map a numeric unit id (e.g. a template's defaultUnitId) to its
    human-readable dimension/category (mass, volume, temperature, ...).
    Returns None if the id is unknown.
    """
    from rspace_client.inv import quantity_unit as qu
    for unit in qu.QuantityUnit.data:
        if unit["id"] == unit_id:
            return unit["category"]
    return None


@mcp.tool(tags={"rspace", "inventory", "samples"})
def create_sample(
    name: str,
    tags: List[str] = None,
    description: str = None,
    subsample_count: int = 1,
    total_quantity_value: float = None,
    total_quantity_unit: str = "ml"
) -> dict:
    """
    Creates a new sample in the inventory system
    
    Usage: Register new samples with metadata and quantity tracking
    Subsamples: Automatically creates specified number of subsample aliquots
    Quantity: Tracks total amount with specified units (ml, mg, μl, etc.)
    
    Returns: Created sample information including generated subsample IDs
    """
    tag_objects = i.gen_tags(tags) if tags else []
    
    quantity = None
    if total_quantity_value:
        unit = _resolve_quantity_unit(total_quantity_unit)
        quantity = i.Quantity(total_quantity_value, unit)
    
    return inv_cli.create_sample(
        name=name,
        tags=tag_objects,
        description=description,
        subsample_count=subsample_count,
        total_quantity=quantity
    )


def _build_link_field_value(field_name: str, value: Any) -> dict:
    """Serialise a caller-supplied value for a Link custom field.

    A Link field does not hold text: it points at another RSpace record with a
    typed, optionally version-pinned relationship. The caller supplies a dict
    describing the target and the relationship, e.g.
        {"relationType": "References", "targetGlobalId": "SA123"}
    snake_case keys (relation_type / target_global_id / version_pin) are also
    accepted. Returns the API "link" payload
    {"relationType": ..., "targetGlobalId": ..., "versionPin": ...}.

    Validation (target global-id prefix, relationType vocabulary) is delegated to
    the client's InventoryLink so the server stays the source of truth.
    """
    if not isinstance(value, dict):
        raise ValueError(
            f"Link field {field_name!r} value must be a dict with 'relationType' and "
            f"'targetGlobalId', e.g. {{'relationType': 'References', 'targetGlobalId': 'SA123'}}; "
            f"got {value!r}"
        )
    relation = value.get("relationType", value.get("relation_type"))
    target = value.get("targetGlobalId", value.get("target_global_id"))
    version = value.get("versionPin", value.get("version_pin"))
    if not relation or not target:
        raise ValueError(
            f"Link field {field_name!r} requires both 'relationType' and 'targetGlobalId'; "
            f"got {value!r}"
        )
    return i.InventoryLink(relation, target, version)._toDict()


@mcp.tool(tags={"rspace", "inventory", "samples"})
def create_sample_from_template(
    template_id: str,
    name: str,
    fields: Dict[str, Any] = None,
    tags: List[str] = None,
    description: str = None,
    subsample_count: int = 1,
    total_quantity_value: float = None,
    total_quantity_unit: str = "ml"
) -> dict:
    """
    Creates a new sample based on an existing sample template.

    Recommended workflow:
      1. list_sample_templates  — find the right template and note its global ID (e.g. "IT12")
      2. get_sample_template    — inspect field names, types, allowed options, and which are mandatory
      3. create_sample_from_template — create the sample, supplying values for the fields you want set

    template_id:
      Must use the global ID format with the "IT" prefix, e.g. "IT12" (not just the number).
      This avoids ambiguity with other RSpace resource types that share numeric IDs.

    fields:
      A dict of field name → value for the template's custom fields. Only include fields
      you want to set — blank fields are sent automatically so the API accepts the request.

      IMPORTANT: the API requires all template fields to be present in the request, even
      optional ones left blank (e.g. date fields). This tool handles that automatically.

      Value format by field type:
        String / Text / Number   →  plain value          e.g. {"Concentration": "5"}
        Date / Time              →  ISO 8601 string      e.g. {"Receipt date": "2024-03-15"}
        Uri                      →  URL string           e.g. {"Manual": "https://example.com/manual.pdf"}
        Radio                    →  single string from the allowed options
                                                          e.g. {"Antibiotic resistance": "Kanamycin"}
        Choice                   →  list of strings from the allowed options
                                                          e.g. {"Supplier": ["NEB", "Sigma"]}
        Link                     →  a dict pointing at another record, with a typed relationship
                                     {"relationType": <type>, "targetGlobalId": <global id>}
                                     e.g. {"Parent batch": {"relationType": "IsDerivedFrom", "targetGlobalId": "SA84"}}
                                     Optional "versionPin" (int) pins the link to a target version.
                                     relationType must be one of the field's allowedRelationTypes (from
                                     get_sample_template); the target global ID must be an Inventory or ELN
                                     record (SA/SS/IC/IN/IT/SD/NB/GL prefix). A Link field is NOT a plain URL —
                                     use a Uri field for external links.

      If any mandatory fields are omitted, the tool returns an error listing the missing
      fields (names, types, and allowed options where applicable) — re-call with those
      fields included rather than attempting to create the sample.

    quantity:
      Total amount with units (ml, mg, μl, etc.). Only relevant if the template tracks quantity.

    Returns: Created sample dict including global ID and generated subsample IDs.
    """
    if not str(template_id).upper().startswith("IT"):
        return {
            "error": "invalid_template_id",
            "message": (
                f"template_id must be a global ID with the 'IT' prefix, e.g. 'IT{template_id}'. "
                "Use list_sample_templates to find the correct global ID."
            ),
        }

    # Extract the numeric part for the POST body — the API expects a plain integer
    # for templateId, but get_sample_template_by_id handles the full global ID fine.
    numeric_template_id = int(str(template_id)[2:])

    # Fetch the template to validate mandatory fields and build the full field list
    template = inv_cli.get_sample_template_by_id(template_id)
    template_fields = template.get("fields", [])

    # Normalise caller-supplied field names to lowercase for case-insensitive matching
    supplied = {k.lower(): v for k, v in (fields or {}).items()}

    missing_mandatory = [
        {"name": f["name"], "type": f.get("type", "unknown")}
        for f in template_fields
        if f.get("mandatory") and f["name"].lower() not in supplied
    ]

    if missing_mandatory:
        return {
            "error": "mandatory_fields_missing",
            "message": (
                "The template has mandatory fields that must be supplied. "
                "Re-call create_sample_from_template with these fields included in 'fields'."
            ),
            "missing_mandatory_fields": missing_mandatory,
            "all_template_fields": [
                {
                    "name": f["name"],
                    "type": f.get("type", "unknown"),
                    "mandatory": f.get("mandatory", False),
                }
                for f in template_fields
            ],
        }

    # Build the full fields payload in template order.
    # The API requires every template field to be present — omitting even optional/blank
    # fields (e.g. empty date fields) causes a rejection. Fields the caller didn't supply
    # are sent as {} (or {"id": ...}), satisfying the API while leaving the value blank.
    #
    # Value serialisation by field type:
    #   Radio  -> {"selectedOptions": [value]}   single selection, wrapped in list
    #   Choice -> {"selectedOptions": value}      multi-selection; single string auto-wrapped
    #   Link   -> {"link": {"relationType": ..., "targetGlobalId": ...}}   typed record link
    #   Date/Time/String/Number/Uri/… -> {"content": str(value)}
    fields_payload = []
    for tf in template_fields:
        entry = {}
        if "id" in tf:
            entry["id"] = tf["id"]
        value = supplied.get(tf["name"].lower())
        if value is not None:
            field_type = tf.get("type", "").lower()
            if field_type == "radio":
                entry["selectedOptions"] = [str(value)]
            elif field_type == "choice":
                entry["selectedOptions"] = value if isinstance(value, list) else [str(value)]
            elif field_type == "link":
                entry["link"] = _build_link_field_value(tf["name"], value)
            else:
                entry["content"] = str(value)
        # If value is None, entry stays as {} (or {"id": ...}), satisfying the API's
        # requirement that all fields are present while leaving the value blank.
        fields_payload.append(entry)

    tag_objects = i.gen_tags(tags) if tags else []

    quantity = None
    if total_quantity_value:
        unit = _resolve_quantity_unit(total_quantity_unit)
        quantity = i.Quantity(total_quantity_value, unit)

    return inv_cli.create_sample(
        name=name,
        tags=tag_objects,
        description=description,
        sample_template_id=numeric_template_id,
        fields=fields_payload,
        subsample_count=subsample_count,
        total_quantity=quantity
    )


@mcp.tool(tags={"rspace", "inventory", "samples"})
def get_sample(sample_id: Union[int, str]) -> dict:
    """
    Retrieves complete information about a specific sample
    
    Usage: Get detailed sample metadata, location, and subsample information
    Parameters: sample_id can be numeric ID or global ID (e.g., "SA12345")
    Returns: Full sample details including all subsamples
    """
    return inv_cli.get_sample_by_id(sample_id)


@mcp.tool(tags={"rspace", "inventory", "samples"})
def get_subsample(subsample_id: Union[int, str]) -> dict:
    """
    Retrieves complete information about a specific subsample

    Usage: Inspect a single subsample's metadata, parent sample, and storage
    location without listing the whole sample
    Parameters: subsample_id can be numeric ID or global ID (e.g., "SS12345")
    Returns: Full subsample details
    """
    return inv_cli.get_subsample_by_id(subsample_id)


@mcp.tool(tags={"rspace", "inventory", "samples"})
def list_subsamples(page_size: int = 20, page_number: int = 0,
                    order_by: str = "modificationDate", sort_order: str = "desc") -> dict:
    """
    Lists subsamples in the inventory with pagination and sorting

    Usage: Browse subsamples directly without traversing parent samples
    Sorting: order_by must be one of: name, type, globalId, creationDate,
             modificationDate. sort_order is "asc" or "desc".
    Returns: Paginated list of subsample metadata
    """
    pagination = i.Pagination(page_size=page_size, page_number=page_number,
                              order_by=order_by, sort_order=sort_order)
    return inv_cli.list_subsamples(pagination)


@mcp.tool(tags={"rspace", "inventory", "samples"})
def delete_sample(sample_id: Union[int, str]) -> dict:
    """
    Deletes (trashes) a sample and its subsamples

    Usage: Remove a sample from active inventory
    Behaviour: Soft-delete — the item is moved to trash; cannot be undone
    via this MCP. Do not call on samples whose subsamples are still placed
    in containers if you want to keep the container intact.
    Returns: A confirmation dict {"success": True, "deleted": <sample_id>}
    """
    inv_cli.delete_sample(sample_id)
    return {"success": True, "deleted": str(sample_id)}


@mcp.tool(tags={"rspace", "inventory", "samples"})
def delete_subsample(subsample_id: Union[int, str]) -> dict:
    """
    Deletes (trashes) a single subsample

    Usage: Remove an aliquot without affecting its parent sample's other
    subsamples
    Returns: API confirmation
    """
    sid = str(subsample_id)
    numeric = int(sid[2:]) if sid.upper().startswith("SS") else int(sid)
    return inv_cli.doDelete("subSamples", numeric)


@mcp.tool(tags={"rspace", "inventory", "containers"})
def delete_container(container_id: Union[int, str]) -> dict:
    """
    Deletes (trashes) a container

    Usage: Remove a container from active inventory
    Restriction: The container must be empty — the API rejects deletion
    of a container that still has items in any of its locations
    Returns: The trashed container dict
    """
    cid = str(container_id)
    numeric = int(cid[2:]) if cid.upper().startswith(("BC", "IC", "GC", "LC")) else int(cid)
    return inv_cli.doDelete("containers", numeric)


@mcp.tool(tags={"rspace", "inventory", "templates"})
def delete_sample_template(template_id: Union[int, str]) -> dict:
    """
    Deletes a sample template

    Usage: Remove a template that is no longer needed
    Returns: A confirmation dict {"success": True, "deleted": <template_id>}
    """
    inv_cli.delete_sample_template(template_id)
    return {"success": True, "deleted": str(template_id)}


@mcp.tool(tags={"rspace", "inventory", "samples"})
def list_samples(page_size: int = 20, page_number: int = 0,
                 order_by: str = "modificationDate", sort_order: str = "desc") -> dict:
    """
    Lists samples in the inventory with pagination and sorting

    Usage: Browse sample collection, find recent additions
    Sorting: order_by must be one of: name, type, globalId, creationDate,
             modificationDate. sort_order is "asc" or "desc".
    Returns: Paginated list of sample metadata
    """
    pagination = i.Pagination(page_size=page_size, page_number=page_number,
                              order_by=order_by, sort_order=sort_order)
    return inv_cli.list_samples(pagination)


@mcp.tool(tags={"rspace", "inventory", "samples"})
def duplicate_sample(sample_id: Union[int, str], new_name: str = None) -> dict:
    """
    Creates an exact copy of an existing sample
    
    Usage: Replicate samples for parallel experiments or backup
    Returns: New sample information with fresh ID and subsamples
    """
    return inv_cli.duplicate(sample_id, new_name)


@mcp.tool(tags={"rspace", "inventory", "samples"})
def split_subsample(
    subsample_id: Union[int, str], 
    num_new_subsamples: int,
    quantity_per_subsample: float = None
) -> dict:
    """
    Divides a subsample into multiple new subsamples
    
    Usage: Create aliquots for distribution or different experiments
    Quantity: If specified, each new subsample gets this amount
    Returns: Information about newly created subsamples
    """
    return inv_cli.split_subsample(subsample_id, num_new_subsamples, quantity_per_subsample)


@mcp.tool(tags={"rspace", "inventory", "samples"})
def add_note_to_subsample(subsample_id: Union[int, str], note: str) -> dict:
    """
    Adds annotations or observations to a specific subsample
    
    Usage: Record experimental notes, observations, or handling instructions
    Returns: Updated subsample information with new note
    """
    return inv_cli.add_note_to_subsample(subsample_id, note)


# ==================== SEARCH AND DISCOVERY ====================
# Tools for finding inventory items across the system

@mcp.tool(tags={"rspace", "inventory", "samples"})
def search_inventory(query: str, result_type: str = None) -> dict:
    """
    Searches across all inventory items using text query
    
    Usage: Find samples, containers, or templates by name, tags, or description
    Result types: 'SAMPLE', 'SUBSAMPLE', 'CONTAINER', 'TEMPLATE' (or None for all)
    Returns: Matching items with relevance scoring
    """
    rt = None
    if result_type:
        rt = getattr(i.ResultType, result_type.upper(), None)
    return inv_cli.search(query, result_type=rt)


# ==================== CONTAINER MANAGEMENT ====================
# Tools for creating and managing storage containers

@mcp.tool(tags={"rspace", "inventory", "containers"})
def create_list_container(
    name: str,
    description: str = None,
    tags: List[str] = None,
    can_store_containers: bool = True,
    can_store_samples: bool = True,
    parent_container_id: Optional[Union[int, str]] = None
) -> dict:
    """
    Creates a simple list-based container for organizing inventory
    
    Usage: Create folders, boxes, or other containers without specific positioning
    Storage permissions: Configure what types of items can be stored
    Hierarchy: Optionally nest within another container
    
    Returns: Created container information with storage settings
    """
    tag_objects = i.gen_tags(tags) if tags else []
    
    location = i.TopLevelTargetLocation()
    if parent_container_id:
        location = i.ListContainerTargetLocation(parent_container_id)
    
    return inv_cli.create_list_container(
        name=name,
        description=description,
        tags=tag_objects,
        can_store_containers=can_store_containers,
        can_store_samples=can_store_samples,
        location=location
    )


@mcp.tool(tags={"rspace", "inventory", "containers"})
def create_grid_container(
    name: str,
    rows: int,
    columns: int,
    description: str = None,
    tags: List[str] = None,
    can_store_containers: bool = True,
    can_store_samples: bool = True,
    parent_container_id: Optional[Union[int, str]] = None
) -> dict:
    """
    Creates a grid-based container with specific positioning
    
    Usage: Create microplates, freezer boxes, or other position-specific storage
    Dimensions: Define exact grid size (e.g., 8x12 for 96-well plate)
    Positioning: Items placed at specific coordinates (row, column)
    
    Returns: Created container information with grid specifications
    """
    tag_objects = i.gen_tags(tags) if tags else []
    
    location = i.TopLevelTargetLocation()
    if parent_container_id:
        location = i.ListContainerTargetLocation(parent_container_id)
    
    return inv_cli.create_grid_container(
        name=name,
        row_count=rows,
        column_count=columns,
        description=description,
        tags=tag_objects,
        can_store_containers=can_store_containers,
        can_store_samples=can_store_samples,
        location=location
    )


@mcp.tool(tags={"rspace", "inventory", "containers"})
def create_image_container(
    name: str,
    image_path: str,
    locations: List[List[int]] = None,
    description: str = None,
    tags: List[str] = None,
    can_store_containers: bool = True,
    can_store_samples: bool = True,
    parent_container_id: Optional[Union[int, str]] = None
) -> dict:
    """
    Creates an image-based container with marked locations on a background image

    Usage: Visualise storage layouts that don't fit a regular grid (bench photos,
    cryo-rack diagrams, microscope slide maps)
    Image: Provide a local file path to a PNG/JPEG; encoded and uploaded by server
    Locations: Optional list of [x, y] pixel coordinates marking storable spots.
    Each returned location includes a server-assigned id needed for placing items
    via move_items_to_image_container — read them from the response.

    Returns: Created container with locations[].id values
    """
    if not os.path.isfile(image_path):
        raise ValueError(f"image_path does not exist: {image_path}")

    tag_objects = i.gen_tags(tags) if tags else []
    location = i.TopLevelTargetLocation()
    if parent_container_id:
        location = i.ListContainerTargetLocation(parent_container_id)

    coord_tuples = [tuple(p) for p in (locations or [])]

    post = i.ImageContainerPost(
        name=name,
        image_file=image_path,
        locations=coord_tuples,
        tags=tag_objects,
        description=description,
        can_store_containers=can_store_containers,
        can_store_samples=can_store_samples,
        location=location,
    )
    return inv_cli.create_image_container(post)


@mcp.tool(tags={"rspace", "inventory", "containers"})
def add_image_container_locations(
    container_id: Union[int, str],
    locations: List[List[int]]
) -> dict:
    """
    Adds new marker locations to an existing image container

    Usage: Iteratively refine an image container's location markers without
    recreating it
    Locations: List of [x, y] pixel coordinates
    Returns: Updated image container including all locations with their ids
    """
    coord_tuples = [tuple(p) for p in locations]
    return inv_cli.add_locations_to_image_container(container_id, *coord_tuples)


@mcp.tool(tags={"rspace", "inventory", "containers"})
def delete_image_container_locations(
    container_id: Union[int, str],
    location_ids: List[int]
) -> dict:
    """
    Removes marker locations from an image container

    Usage: Clean up unused or mistaken markers
    Note: Locations occupied by items cannot be deleted
    Returns: Updated image container
    """
    return inv_cli.delete_locations_from_image_container(container_id, *location_ids)


@mcp.tool(tags={"rspace", "inventory"})
def set_item_image(item_id: Union[int, str], image_path: str) -> dict:
    """
    Sets or replaces the image for a sample, subsample, or container

    Usage: Attach a photo to inventory items, or swap the background of an
    existing image container
    Returns: Updated item with image and thumbnail links
    """
    if not os.path.isfile(image_path):
        raise ValueError(f"image_path does not exist: {image_path}")
    with open(image_path, "rb") as f:
        return inv_cli.set_image(item_id, f)


@mcp.tool(tags={"rspace", "inventory", "containers"})
def get_container(container_id: Union[int, str], include_content: bool = False) -> dict:
    """
    Retrieves container information with optional content listing
    
    Usage: Examine container properties and optionally see what's inside
    Performance: Set include_content=False for faster queries on large containers
    Returns: Container details and optionally contained items
    """
    return inv_cli.get_container_by_id(container_id, include_content)


@mcp.tool(tags={"rspace", "inventory", "containers"})
def list_containers(page_size: int = 20, page_number: int = 0) -> dict:
    """
    Lists top-level containers (not nested within other containers)

    Usage: Browse main container organization structure
    Pagination: page_number is 0-based
    Returns: Paginated list of root-level containers
    """
    pagination = i.Pagination(page_size=page_size, page_number=page_number)
    return inv_cli.list_top_level_containers(pagination)


@mcp.tool(tags={"rspace", "inventory", "containers"})
def get_workbenches() -> List[dict]:
    """
    Retrieves all available workbenches (virtual workspaces)
    
    Usage: Find available workspaces for organizing current work
    Workbenches: Special containers representing physical or logical workspaces
    Returns: List of all workbench containers
    """
    return inv_cli.get_workbenches()


# ==================== ITEM MOVEMENT AND ORGANIZATION ====================
# Tools for moving samples and containers between locations

@mcp.tool(tags={"rspace", "inventory", "movement"})
def move_items_to_list_container(
    target_container_id: Union[int, str],
    item_ids: List[str]
) -> dict:
    """
    Moves multiple items to a list-based container
    
    Usage: Organize items in simple containers without specific positioning
    Items: Can move both samples/subsamples and other containers
    Returns: Success status and results for each moved item
    """
    result = inv_cli.add_items_to_list_container(target_container_id, *item_ids)
    return _bulk_result(result)


@mcp.tool(tags={"rspace", "inventory", "movement"})
def move_items_to_grid_container_by_row(
    target_container_id: Union[int, str],
    item_ids: List[str],
    start_column: int = 1,
    start_row: int = 1,
    total_columns: int = None,
    total_rows: int = None
) -> dict:
    """
    Moves items to grid container, filling positions row by row
    
    Usage: Systematic filling of plates, boxes, or other gridded containers
    Auto-positioning: Automatically calculates next available positions
    Dimensions: Auto-detected from container if not provided
    
    Returns: Success status and final positions of moved items
    """
    # Auto-detect container dimensions if not provided
    if total_columns is None or total_rows is None:
        container = inv_cli.get_container_by_id(target_container_id)
        container_obj = i.Container.of(container)
        if hasattr(container_obj, 'column_count'):
            total_columns = container_obj.column_count()
            total_rows = container_obj.row_count()
        else:
            raise ValueError("Container dimensions required for non-grid containers")
    
    placement = i.ByRow(start_column, start_row, total_columns, total_rows, *item_ids)
    result = inv_cli.add_items_to_grid_container(target_container_id, placement)
    return _bulk_result(result)


@mcp.tool(tags={"rspace", "inventory", "movement"})
def move_items_to_grid_container_by_column(
    target_container_id: Union[int, str],
    item_ids: List[str],
    start_column: int = 1,
    start_row: int = 1,
    total_columns: int = None,
    total_rows: int = None
) -> dict:
    """
    Moves items to grid container, filling positions column by column
    
    Usage: Alternative filling pattern for specific experimental layouts
    Auto-positioning: Fills down columns before moving to next column
    Returns: Success status and final positions of moved items
    """
    # Auto-detect container dimensions if not provided
    if total_columns is None or total_rows is None:
        container = inv_cli.get_container_by_id(target_container_id)
        container_obj = i.Container.of(container)
        if hasattr(container_obj, 'column_count'):
            total_columns = container_obj.column_count()
            total_rows = container_obj.row_count()
        else:
            raise ValueError("Container dimensions required for non-grid containers")
    
    placement = i.ByColumn(start_column, start_row, total_columns, total_rows, *item_ids)
    result = inv_cli.add_items_to_grid_container(target_container_id, placement)
    return _bulk_result(result)


@mcp.tool(tags={"rspace", "inventory", "movement"})
def move_items_to_specific_grid_locations(
    target_container_id: Union[int, str],
    item_ids: List[str],
    grid_locations: List[GridLocation]
) -> dict:
    """
    Places items at specific coordinates within a grid container
    
    Usage: Precise positioning for experimental layouts or protocols
    Coordinates: Each item gets an exact (row, column) position
    Validation: Ensures equal number of items and positions
    
    Returns: Success status and confirmation of final positions
    """
    if len(item_ids) != len(grid_locations):
        raise ValueError("Number of items must match number of grid locations")
    
    locations = [i.GridLocation(loc.x, loc.y) for loc in grid_locations]
    placement = i.ByLocation(locations, *item_ids)
    result = inv_cli.add_items_to_grid_container(target_container_id, placement)
    return _bulk_result(result)


@mcp.tool(tags={"rspace", "inventory", "movement"})
def move_items_to_image_container(
    target_container_id: Union[int, str],
    item_ids: List[str],
    location_ids: List[int]
) -> dict:
    """
    Places items at specific marker locations within an image container

    Usage: Populate an image container by mapping items to its predefined
    location markers
    Location IDs: The numeric ids of locations on the image container — get them
    from create_image_container's response or get_container output
    Validation: items and location_ids are zipped pairwise; extras are ignored

    Returns: Success status and per-item placement results
    """
    result = inv_cli.add_items_to_image_container(target_container_id, item_ids, location_ids)
    return _bulk_result(result)


# ==================== TEMPLATE MANAGEMENT ====================
# Tools for creating and using sample templates for standardization

@mcp.tool(tags={"rspace", "inventory", "templates"})
def create_sample_template(template_data: dict) -> dict:
    """
    Creates a reusable template for sample creation

    Usage: Standardize sample creation with predefined fields and validation
    Template data: A dict with a mandatory "name", a "defaultUnitId" (the quantity
      unit id, e.g. 3 for ml) and a "fields" list, e.g.
        {"name": "Antibody template", "defaultUnitId": 3,
         "fields": [{"name": "Clone", "type": "string"},
                    {"name": "Concentration", "type": "number"},
                    {"name": "Parent batch", "type": "link",
                     "allowedRelationTypes": ["IsDerivedFrom"]}]}
      Supported field types: string, text, number, date, time, radio, choice,
      attachment, uri, link. Radio/choice fields take a "definition": {"options": [...]}.
      A link field defines a typed relationship to another record (not a URL — use
      uri for URLs). It may optionally whitelist which relationships are allowed via
      "allowedRelationTypes"; omitting it permits all relationship types. Relationship
      types come from the DataCite vocabulary plus IsCalibratedBy/Calibrates
      (e.g. References, IsDerivedFrom, IsDescribedBy, HasPart, IsCalibratedBy).
    Returns: Created template including its global ID (IT...)
    """
    return inv_cli.create_sample_template(template_data)


@mcp.tool(tags={"rspace", "inventory", "templates"})
def get_sample_template(template_id: str) -> dict:
    """
    Retrieves detailed information about a sample template

    Usage: Examine template structure before using for sample creation.
           Call this before create_sample_from_template to discover available
           fields, their types, and which are mandatory.
    Template ID: Use the global ID with the "IT" prefix, e.g. "IT12".
                 Use list_sample_templates to find global IDs.
    Returns: Complete template definition including field specifications. When the
             template tracks quantity, the result is enriched with a readable
             "defaultUnitDimension" (e.g. "mass", "volume") alongside the opaque
             numeric "defaultUnitId", so callers know which unit dimension
             create_sample_from_template must use for this template.
    """
    template = inv_cli.get_sample_template_by_id(template_id)
    if isinstance(template, dict) and template.get("defaultUnitId") is not None:
        dimension = _unit_dimension(template["defaultUnitId"])
        if dimension is not None:
            template["defaultUnitDimension"] = dimension
    return template


@mcp.tool(tags={"rspace", "inventory", "templates"})
def list_sample_templates(page_size: int = 20, page_number: int = 0) -> dict:
    """
    Lists available sample templates for reuse

    Usage: Browse existing templates before creating new samples
    Pagination: page_number is 0-based
    Returns: Paginated list of template metadata
    """
    pagination = i.Pagination(page_size=page_size, page_number=page_number)
    return inv_cli.list_sample_templates(pagination)


# ==================== INSTRUMENTS AND INSTRUMENT TEMPLATES ====================
# Instruments are a native Inventory item type (RSpace 2.24+). Like samples,
# they are created from a template that defines their custom fields. Instrument
# records use the "IN" global-id prefix; instrument templates use "NT".
#
# Note: the generic utility tools also work on instruments once created —
# rename_inventory_item, set_item_image, add_extra_fields_to_item and
# generate_barcode all accept an instrument (IN...) or template (NT...) id.

@mcp.tool(tags={"rspace", "inventory", "instruments", "templates"})
def create_instrument_template(template_data: dict) -> dict:
    """
    Creates a reusable template for instrument creation

    Usage: Standardize instrument registration with predefined custom fields
    Template data: A dict with a mandatory "name" and an optional "fields" list,
      e.g. {"name": "Microscope template",
            "fields": [{"name": "Serial Number", "type": "string"},
                       {"name": "Calibration", "type": "number"}]}
      Supported field types: string, text, number, date, time, radio, choice,
      attachment, uri, link. Radio/choice fields take a "definition": {"options": [...]}.
      A link field defines a typed relationship to another record (not a URL, use
      uri for URLs). It may optionally whitelist which relationships are allowed via
      "allowedRelationTypes", e.g.
        {"name": "Calibrated by", "type": "link",
         "allowedRelationTypes": ["IsCalibratedBy"]}
      Omitting allowedRelationTypes permits all relationship types. Relationship
      types come from the DataCite vocabulary plus IsCalibratedBy/Calibrates
      (e.g. References, IsDerivedFrom, IsDescribedBy, HasPart, IsCalibratedBy).
      Unlike sample templates, instrument templates have no default unit.

      tags: optional list of tags. Plain strings are accepted and wrapped
      automatically, e.g. "tags": ["microscopy"]. Objects of the form
      {"value": "microscopy"} are also accepted and passed through unchanged.
    Returns: Created instrument template including its global ID (NT...)
    """
    if isinstance(template_data, dict) and template_data.get("tags"):
        # The inventory API rejects bare strings for tags (needs ApiTagInfo
        # objects). Sample/container tools get this for free via i.gen_tags;
        # this tool takes a raw dict, so normalise the tags here instead.
        template_data = {**template_data, "tags": _normalise_inventory_tags(template_data["tags"])}
    return inv_cli.create_instrument_template(template_data)


@mcp.tool(tags={"rspace", "inventory", "instruments", "templates"})
def get_instrument_template(template_id: str) -> dict:
    """
    Retrieves detailed information about an instrument template

    Usage: Examine template structure before using for instrument creation.
           Call this before create_instrument_from_template to discover available
           fields, their types, and which are mandatory.
    Template ID: Use the global ID with the "NT" prefix, e.g. "NT12".
                 Use list_instrument_templates to find global IDs.
    Returns: Complete template definition including field specifications
    """
    return inv_cli.get_instrument_template_by_id(template_id)


@mcp.tool(tags={"rspace", "inventory", "instruments", "templates"})
def list_instrument_templates(page_size: int = 20, page_number: int = 0) -> dict:
    """
    Lists available instrument templates for reuse

    Usage: Browse existing templates before creating new instruments
    Pagination: page_number is 0-based
    Returns: Paginated list of template metadata
    """
    pagination = i.Pagination(page_size=page_size, page_number=page_number)
    return inv_cli.list_instrument_templates(pagination)


@mcp.tool(tags={"rspace", "inventory", "instruments", "templates"})
def delete_instrument_template(template_id: Union[int, str]) -> dict:
    """
    Deletes an instrument template

    Usage: Remove an instrument template that is no longer needed
    Returns: A confirmation dict {"success": True, "deleted": <template_id>}
    """
    inv_cli.delete_instrument_template(template_id)
    return {"success": True, "deleted": str(template_id)}


@mcp.tool(tags={"rspace", "inventory", "instruments"})
def create_instrument(
    name: str,
    tags: List[str] = None,
    description: str = None,
) -> dict:
    """
    Creates a new instrument in the inventory system

    Usage: Register a new instrument with basic metadata. If no template is
      specified the default Basic Instrument template is used, giving an
      instrument with no custom fields. To create an instrument with template
      fields populated, use create_instrument_from_template instead.
    Returns: Created instrument information including its global ID (IN...)
    """
    tag_objects = i.gen_tags(tags) if tags else []
    return inv_cli.create_instrument(
        name=name,
        tags=tag_objects,
        description=description,
    )


@mcp.tool(tags={"rspace", "inventory", "instruments"})
def create_instrument_from_template(
    template_id: str,
    name: str,
    fields: Dict[str, Any] = None,
    tags: List[str] = None,
    description: str = None,
) -> dict:
    """
    Creates a new instrument based on an existing instrument template.

    Recommended workflow:
      1. list_instrument_templates  — find the right template and note its global ID (e.g. "NT12")
      2. get_instrument_template    — inspect field names, types, allowed options, and which are mandatory
      3. create_instrument_from_template — create the instrument, supplying values for the fields you want set

    template_id:
      Must use the global ID format with the "NT" prefix, e.g. "NT12" (not just the number).
      This avoids ambiguity with other RSpace resource types that share numeric IDs.

    fields:
      A dict of field name → value for the template's custom fields. Only include fields
      you want to set — blank fields are sent automatically so the API accepts the request.

      Value format by field type:
        String / Text / Number   →  plain value          e.g. {"Serial Number": "SN-1234"}
        Date / Time              →  ISO 8601 string      e.g. {"Last serviced": "2024-03-15"}
        Uri                      →  URL string           e.g. {"Manual": "https://example.com/manual.pdf"}
        Radio                    →  single string from the allowed options
        Choice                   →  list of strings from the allowed options
        Link                     →  a dict pointing at another record, with a typed relationship
                                     {"relationType": <type>, "targetGlobalId": <global id>}
                                     e.g. {"Calibrated by": {"relationType": "IsCalibratedBy", "targetGlobalId": "IN12"}}
                                     Optional "versionPin" (int) pins the link to a target version.
                                     relationType must be one of the field's allowedRelationTypes (from
                                     get_instrument_template). A Link field is NOT a plain URL — use a Uri
                                     field for external links.

      If any mandatory fields are omitted, the tool returns an error listing the missing
      fields (names, types, and allowed options where applicable) — re-call with those
      fields included rather than attempting to create the instrument.

    Returns: Created instrument dict including its global ID (IN...).
    """
    if not str(template_id).upper().startswith("NT"):
        return {
            "error": "invalid_template_id",
            "message": (
                f"template_id must be a global ID with the 'NT' prefix, e.g. 'NT{template_id}'. "
                "Use list_instrument_templates to find the correct global ID."
            ),
        }

    # Extract the numeric part for the POST body — the API expects a plain integer
    # for templateId, but get_instrument_template_by_id handles the full global ID fine.
    numeric_template_id = int(str(template_id)[2:])

    # Fetch the template to validate mandatory fields and build the full field list
    template = inv_cli.get_instrument_template_by_id(template_id)
    template_fields = template.get("fields", [])

    # Normalise caller-supplied field names to lowercase for case-insensitive matching
    supplied = {k.lower(): v for k, v in (fields or {}).items()}

    missing_mandatory = [
        {"name": f["name"], "type": f.get("type", "unknown")}
        for f in template_fields
        if f.get("mandatory") and f["name"].lower() not in supplied
    ]

    if missing_mandatory:
        return {
            "error": "mandatory_fields_missing",
            "message": (
                "The template has mandatory fields that must be supplied. "
                "Re-call create_instrument_from_template with these fields included in 'fields'."
            ),
            "missing_mandatory_fields": missing_mandatory,
            "all_template_fields": [
                {
                    "name": f["name"],
                    "type": f.get("type", "unknown"),
                    "mandatory": f.get("mandatory", False),
                }
                for f in template_fields
            ],
        }

    # Build the full fields payload in template order. As with samples, the API
    # requires every template field to be present — fields the caller didn't supply
    # are sent as {} (or {"id": ...}), leaving the value blank.
    #   Radio  -> {"selectedOptions": [value]}
    #   Choice -> {"selectedOptions": value}   (single string auto-wrapped)
    #   Link   -> {"link": {"relationType": ..., "targetGlobalId": ...}}   typed record link
    #   Date/Time/String/Number/Uri/… -> {"content": str(value)}
    fields_payload = []
    for tf in template_fields:
        entry = {}
        if "id" in tf:
            entry["id"] = tf["id"]
        value = supplied.get(tf["name"].lower())
        if value is not None:
            field_type = tf.get("type", "").lower()
            if field_type == "radio":
                entry["selectedOptions"] = [str(value)]
            elif field_type == "choice":
                entry["selectedOptions"] = value if isinstance(value, list) else [str(value)]
            elif field_type == "link":
                entry["link"] = _build_link_field_value(tf["name"], value)
            else:
                entry["content"] = str(value)
        fields_payload.append(entry)

    tag_objects = i.gen_tags(tags) if tags else []

    return inv_cli.create_instrument(
        name=name,
        tags=tag_objects,
        description=description,
        instrument_template_id=numeric_template_id,
        fields=fields_payload,
    )


@mcp.tool(tags={"rspace", "inventory", "instruments"})
def get_instrument(instrument_id: Union[int, str]) -> dict:
    """
    Retrieves complete information about a single instrument

    Usage: Get full instrument details including custom field values
    Parameters: instrument_id can be a numeric ID or a global ID (e.g. "IN123")
    Returns: Full instrument description
    """
    return inv_cli.get_instrument_by_id(instrument_id)


@mcp.tool(tags={"rspace", "inventory", "instruments"})
def list_instruments(page_size: int = 20, page_number: int = 0) -> dict:
    """
    Lists instruments visible to the current user

    Usage: Browse registered instruments
    Pagination: page_number is 0-based
    Returns: Paginated list of instrument metadata
    """
    pagination = i.Pagination(page_size=page_size, page_number=page_number)
    return inv_cli.list_instruments(pagination)


@mcp.tool(tags={"rspace", "inventory", "instruments"})
def delete_instrument(instrument_id: Union[int, str]) -> dict:
    """
    Deletes (marks as deleted) an instrument

    Usage: Remove an instrument from Inventory listings. Can be reversed by an
      admin/owner via restore in the RSpace UI.
    Parameters: instrument_id can be a numeric ID or a global ID (e.g. "IN123")
    Returns: A confirmation dict {"success": True, "deleted": <instrument_id>}
    """
    inv_cli.delete_instrument(instrument_id)
    return {"success": True, "deleted": str(instrument_id)}


# ==================== UTILITY AND HELPER FUNCTIONS ====================
# General-purpose tools for inventory management and optimization

@mcp.tool(tags={"rspace", "inventory", "utility"})
def rename_inventory_item(item_id: Union[int, str], new_name: str) -> dict:
    """
    Changes the name of any inventory item
    
    Usage: Rename samples, subsamples, containers, or templates
    Universal: Works with any inventory item type
    Returns: Updated item information with new name
    """
    return inv_cli.rename(item_id, new_name)


@mcp.tool(tags={"rspace", "inventory", "utility"})
def update_inventory_item_tags(
    item_id: Union[int, str],
    tags: List[str],
    mode: Literal["append", "replace"] = "append",
) -> dict:
    """
    Adds or replaces tags on an existing inventory item.

    Usage: Retag an item after creation. The create_* tools only accept tags at
      creation time; this is the inventory-side counterpart to
      tagDocumentOrNotebookEntry / remove_tags_from_document (which act on ELN
      documents). Works with any inventory item type: samples, subsamples,
      containers, sample templates, instruments, and instrument templates.

    Parameters:
    - item_id: global ID including its type prefix (SA/SS/IC/IT/IN/NT), e.g.
      "SA123". A bare numeric ID is rejected because the type cannot be inferred.
    - tags: tag values as plain strings, e.g. ["chemistry", "workshop"].
    - mode:
        "append"  (default) — add these tags to the item's existing ones,
                    de-duplicated case-insensitively; existing tags are kept.
        "replace" — overwrite the item's entire tag set with exactly these tags.

    Returns: The updated item dict, including its full resulting tag set.
    """
    sid = i.Id(item_id)
    if not hasattr(sid, "prefix") or sid.prefix not in i.Id.PREFIX_TO_API:
        return {
            "error": "invalid_item_id",
            "message": (
                f"item_id must be a global ID with a recognised inventory prefix "
                f"(one of {sorted(i.Id.PREFIX_TO_API)}), e.g. 'SA123'. Got {item_id!r}."
            ),
        }

    path = f"/{sid.get_api_endpoint()}/{sid.as_id()}"
    desired = [t.strip() for t in tags if t and t.strip()]

    if mode == "append":
        current = inv_cli.retrieve_api_results(path)
        existing = [t.get("value") for t in (current.get("tags") or []) if t.get("value")]
        seen = {v.lower() for v in existing}
        final_values = list(existing)
        for v in desired:
            if v.lower() not in seen:
                final_values.append(v)
                seen.add(v.lower())
    else:  # replace
        final_values = desired

    return inv_cli.retrieve_api_results(
        path, request_type="PUT", params={"tags": i.gen_tags(final_values)}
    )


@mcp.tool(tags={"rspace", "inventory", "utility"})
def add_extra_fields_to_item(item_id: Union[int, str], field_data: List[dict]) -> dict:
    """
    Adds custom metadata fields to inventory items
    
    Usage: Extend items with experiment-specific or project-specific data
    Field format: [{"name": "Field Name", "type": "text|number|link", "content": "value"}]
    Types:
      'text'   → 'content' holds a string
      'number' → 'content' holds a numeric value
      'link'   → instead of 'content', supply 'relationType' and 'targetGlobalId'
                 (and optional 'versionPin') to point at another record, e.g.
                 {"name": "Derived from", "type": "link",
                  "relationType": "IsDerivedFrom", "targetGlobalId": "SA84"}
                 A link is a typed relationship to an RSpace record, not a URL.

    Returns: Updated item with new custom fields
    """
    type_map = {"text": i.ExtraFieldType.TEXT, "number": i.ExtraFieldType.NUMBER}
    extra_fields = []
    for field in field_data:
        raw_type = str(field.get('type', 'text')).lower()
        if raw_type == "link":
            relation = field.get("relationType", field.get("relation_type"))
            target = field.get("targetGlobalId", field.get("target_global_id"))
            version = field.get("versionPin", field.get("version_pin"))
            if not relation or not target:
                raise ValueError(
                    f"Link extra field {field.get('name')!r} requires 'relationType' and "
                    f"'targetGlobalId'; got {field!r}"
                )
            ef = i.ExtraField.link(field['name'], relation, target, version)
        elif raw_type in type_map:
            ef = i.ExtraField(field['name'], type_map[raw_type], field.get('content', ''))
        else:
            raise ValueError(
                f"Unknown extra field type {raw_type!r} for field "
                f"{field.get('name')!r}; must be one of {sorted(type_map) + ['link']}"
            )
        extra_fields.append(ef)

    return inv_cli.add_extra_fields(item_id, *extra_fields)


@mcp.tool(tags={"rspace", "inventory", "utility"})
def generate_barcode(global_id: str, barcode_type: str = "BARCODE") -> dict:
    """
    Generates scannable barcodes for inventory items

    Usage: Create physical labels for sample tracking and identification
    Types: 'BARCODE' for standard linear barcodes, 'QR' for QR codes
    Returns: dict with `content_type` and `data_base64` (PNG image as base64),
             ready for embedding or saving to disk
    """
    import base64
    bc_type = i.BarcodeFormat.BARCODE if barcode_type.upper() == "BARCODE" else i.BarcodeFormat.QR
    raw = inv_cli.barcode(global_id, barcode_type=bc_type)
    return {
        "content_type": "image/png",
        "data_base64": base64.b64encode(raw).decode("ascii"),
        "size_bytes": len(raw),
    }


# ==================== PERFORMANCE-OPTIMIZED UTILITY FUNCTIONS ====================
# These functions are designed for high-performance operations with large datasets

@mcp.tool(tags={"rspace", "inventory", "utility"})
def get_container_summary(container_id: int | str) -> dict:
    """
    Retrieves container metadata without content for fast queries
    
    Usage: Quick container information lookup without performance impact
    Performance: Avoids loading large content lists for better response times
    Returns: Container metadata only (name, type, capacity, etc.)
    """
    return inv_cli.get_container_by_id(container_id, include_content=False)


@mcp.tool(tags={"rspace", "inventory", "utility"})
def get_container_contents_only(container_id: int | str) -> list:
    """
    Retrieves only the items stored in a container
    
    Usage: Get container contents without metadata overhead
    Performance: Focused query for container content analysis
    Returns: List of contained items with minimal metadata
    """
    container = inv_cli.get_container_by_id(container_id, include_content=True)
    return container.get('locations', [])


@mcp.tool(tags={"rspace", "inventory", "utility"})
def bulk_create_samples(sample_definitions: List[dict]) -> dict:
    """
    Creates multiple samples in a single batch request

    Usage: High-performance sample creation for large datasets — much faster
    than calling create_sample in a loop
    Limit: Up to InventoryClient.MAX_BULK samples per call (raises if exceeded)

    Each entry in sample_definitions accepts the same keys as create_sample:
      - name (required, str)
      - tags (list[str], optional)
      - description (str, optional)
      - subsample_count (int, optional)
      - total_quantity_value (float, optional)
      - total_quantity_unit (str, default "ml" — only used if value supplied)

    Returns: dict with overall success flag, success/error counts, and per-sample
    results in `results`
    """
    if not sample_definitions:
        raise ValueError("sample_definitions must contain at least one sample")
    if len(sample_definitions) > i.InventoryClient.MAX_BULK:
        raise ValueError(
            f"bulk_create_samples accepts at most {i.InventoryClient.MAX_BULK} "
            f"samples per call (got {len(sample_definitions)})"
        )

    posts = []
    for idx, sd in enumerate(sample_definitions):
        if not sd.get("name"):
            raise ValueError(f"sample_definitions[{idx}] missing required 'name'")
        quantity = None
        if sd.get("total_quantity_value") is not None:
            unit = _resolve_quantity_unit(sd.get("total_quantity_unit", "ml"))
            quantity = i.Quantity(sd["total_quantity_value"], unit)
        posts.append(i.SamplePost(
            name=sd["name"],
            tags=i.gen_tags(sd["tags"]) if sd.get("tags") else [],
            description=sd.get("description"),
            subsample_count=sd.get("subsample_count"),
            total_quantity=quantity,
        ))

    return _bulk_result(inv_cli.bulk_create_sample(*posts))


@mcp.tool(tags={"rspace", "inventory", "utility"})
def get_recent_samples_summary(days_back: int = 7, page_size: int = 10) -> list:
    """
    Retrieves recently modified samples with minimal data for dashboard views

    Usage: Quick overview of recent activity without full sample details
    Implementation: Lists samples sorted by lastModified desc and filters
    client-side to those modified within `days_back` days. The RSpace inventory
    API does not currently support server-side date filters for samples.
    Limitation: Only the most recent `page_size` samples are inspected — increase
    page_size if you need a longer window into very active inventories.

    Returns: List of slim sample summaries (globalId, name, lastModified,
    tags, quantity)
    """
    from datetime import datetime, timedelta, timezone

    pagination = i.Pagination(
        page_size=page_size, order_by="modificationDate", sort_order="desc"
    )
    page = inv_cli.list_samples(pagination)
    samples = page.get("samples") or page.get("items") or []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

    def _modified(s):
        ts = s.get("lastModified") or s.get("created")
        if not ts:
            return None
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return None

    out = []
    for s in samples:
        m = _modified(s)
        if m is None or m < cutoff:
            continue
        out.append({
            "globalId": s.get("globalId"),
            "name": s.get("name"),
            "lastModified": s.get("lastModified"),
            "tags": s.get("tags"),
            "quantity": s.get("quantity"),
        })
    return out


# ============================================================================
# LISTS OF MATERIALS (ELN <-> INVENTORY LINKS)
# ============================================================================
# A List of Materials (LoM) links inventory items (samples, subsamples,
# containers) to a text field of an ELN document. These tools wrap the
# corresponding rspace-client InventoryClient methods.

@mcp.tool(tags={"rspace", "inventory", "eln", "lom"})
def create_list_of_materials(
    eln_field_id: int,
    name: str,
    materials: List[str],
    description: Optional[str] = None,
) -> dict:
    """
    Links inventory items to an ELN document field via a List of Materials

    Usage: Record which samples/subsamples/containers were used in an
    experiment by attaching them to a specific text field of an ELN document.
    Parameters:
      - eln_field_id: numeric ID of the ELN document field to attach the list
        to. Obtain it from get_single_Rspace_document — each entry in the
        returned 'fields' has an 'id'.
      - name: a label for the list
      - materials: global IDs of the inventory items to link, e.g.
        ["SA12345", "SS6789", "IC42"] (samples, subsamples, containers)
      - description: optional free-text description of the list's purpose
    Returns: The newly created List of Materials
    """
    return inv_cli.create_list_of_materials(
        eln_field_id, name, *materials, description=description
    )


@mcp.tool(tags={"rspace", "inventory", "eln", "lom"})
def get_lists_of_materials_for_document(document_id: Union[int, str]) -> List[dict]:
    """
    Retrieves all Lists of Materials attached to an ELN document

    Usage: See every inventory item linked anywhere in a document
    Parameters: document_id can be numeric ID or global ID (e.g., "SD12345")
    Returns: A list of the Lists of Materials belonging to the document
    """
    return inv_cli.get_list_of_materials_for_document(document_id)


@mcp.tool(tags={"rspace", "inventory", "eln", "lom"})
def get_lists_of_materials_for_field(field_id: Union[int, str]) -> List[dict]:
    """
    Retrieves all Lists of Materials attached to a single ELN document field

    Usage: See the inventory items linked to one specific field of a document
    Parameters: field_id is the numeric ID of the ELN document field
    Returns: A list of the Lists of Materials belonging to the field
    """
    return inv_cli.get_list_of_materials_for_field(field_id)


@mcp.tool(tags={"rspace", "inventory", "eln", "lom"})
def get_list_of_materials(lom_id: int) -> dict:
    """
    Retrieves a single List of Materials by its ID

    Usage: Inspect the details and linked items of one specific list
    Parameters: lom_id is the numeric ID of the List of Materials
    Returns: The List of Materials
    """
    return inv_cli.get_list_of_materials(lom_id)


# ============================================================================
# SERVER EXECUTION
# ============================================================================
# This section handles the actual MCP server startup
# Modify this section only if changing server configuration or adding
# initialization logic

if __name__ == "__main__":
    """
    Main entry point for the RSpace MCP Server
    
    Extension Guide:
    - Server runs on FastMCP framework with automatic tool discovery
    - All functions decorated with @mcp.tool are automatically registered
    - Tool tags are used for organization and filtering
    - Add new tools anywhere in the file with proper tagging
    
    Deployment:
    - Ensure RSPACE_API_KEY and RSPACE_URL environment variables are set
    - Server will automatically expose all registered tools to MCP clients
    - Use appropriate tags for tool categorization and discovery
    """
    mcp.run()


# ============================================================================
# EXTENSION GUIDELINES FOR CONTRIBUTORS
# ============================================================================
"""
ADDING NEW FUNCTIONALITY:

1. ELN (Electronic Lab Notebook) Extensions:
   - Add new functions in the ELN section with @mcp.tool(tags={"rspace"})
   - Follow existing patterns for error handling and return types
   - Use the eln_cli client for all ELN operations
   - Add comprehensive docstrings explaining usage and parameters

2. Inventory Extensions:
   - Add functions in appropriate inventory subsection
   - Use tags like @mcp.tool(tags={"rspace", "inventory", "category"})
   - Categories: "samples", "containers", "movement", "templates", "utility"
   - Use the inv_cli client for all inventory operations

3. Performance Considerations:
   - Add utility functions for common operations that need optimization
   - Consider bulk operations for high-volume tasks
   - Use appropriate pagination for large result sets
   - Implement content filtering to reduce data transfer

4. Error Handling:
   - Follow existing patterns for input validation
   - Provide meaningful error messages for common failure cases
   - Use appropriate exception types and handle API errors gracefully

5. Documentation:
   - Include comprehensive docstrings for all new functions
   - Explain parameters, return values, and usage examples
   - Document any special requirements or limitations
   - Update this guide when adding new categories or patterns

6. Testing:
   - Test new functions with various input scenarios
   - Verify error handling with invalid inputs
   - Test integration with existing tools and workflows
   - Document any dependencies or setup requirements

COMMON PATTERNS:

- ID Parameters: Accept both numeric IDs and string global IDs
- Pagination: Use appropriate page sizes and provide pagination options
- Tags: Use consistent tagging for organization and discoverability
- Return Types: Return appropriate data structures (dict, list, custom models)
- Optional Parameters: Provide sensible defaults for optional parameters
- Client Usage: Use eln_cli for ELN operations, inv_cli for inventory

ARCHITECTURE NOTES:

- FastMCP Framework: Handles tool registration and server communication
- RSpace Clients: Official Python clients provide API access
- Pydantic Models: Used for type safety and validation
- Environment Config: API credentials loaded from .env file
- Modular Organization: Functions grouped by feature area for maintainability
"""