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

from typing import Annotated, Dict, List, Optional, Union

from fastmcp import FastMCP
from rspace_client.eln import eln as e  # Electronic Lab Notebook client
from rspace_client.inv import inv as i  # Inventory Management client
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
    name: str = Field("document's name")
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
    tags: List[str] = Field(description="Sample tags")
    quantity: Optional[Dict] = Field(description="Sample quantity and units")


class Container(BaseModel):
    """Inventory container metadata"""
    name: str = Field(description="Container name")
    globalId: str = Field(description="Global identifier")
    cType: str = Field(description="Container type (LIST, GRID, WORKBENCH, IMAGE)")
    capacity: Optional[int] = Field(description="Container capacity if applicable")


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

# Initialize RSpace clients
eln_cli = e.ELNClient(api_url, api_key)  # Electronic Lab Notebook operations
inv_cli = i.InventoryClient(api_url, api_key)  # Inventory Management operations


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
def get_documents(page_size: int = 20) -> list[Document]:
    """
    Retrieves recent RSpace documents with pagination
    
    Usage: Get overview of recent documents for browsing/selection
    Limit: Maximum 200 documents per call for performance
    Returns: List of document metadata (not full content)
    """
    if page_size > 200 or page_size < 0:
        raise ValueError("page size must be less than 200")
    resp = eln_cli.get_documents(page_size=page_size)
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
    form_id: int | str = None,
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

@mcp.tool(tags={"rspace"}, name="tagDocumentOrNotebookEntry")
def tag_document(
        doc_id: int | str,
        tags: Annotated[List[str], Field(description="One or more tags in a list")]
) -> Dict[str, any]:
    """
    Adds tags to documents for organization and searchability
    
    Usage: Categorize documents by project, experiment type, etc.
    Tags: Use consistent naming for better organization
    Returns: Updated document with new tags
    """
    resp = eln_cli.update_document(document_id=doc_id, tags=tags)
    return resp


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
    parent_folder_id: int | str = None,
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
    resp = eln_cli.get_activity(users=[username], global_id=global_id, date_from=date_from, date_to=date_to)
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
    resp = eln_cli.download_file(file_id=file_id, filename=file_path, chunk_size=1024)
    return resp


# ============================================================================
# INVENTORY MANAGEMENT TOOLS
# ============================================================================
# This section contains all tools related to sample management, container
# organization, and inventory tracking. When adding new inventory features,
# organize them by category (samples, containers, movement, templates, utility).

# ==================== SAMPLE MANAGEMENT ====================
# Core sample creation, retrieval, and manipulation tools

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
        from rspace_client.inv import quantity_unit as qu
        unit = qu.QuantityUnit.of(total_quantity_unit)
        quantity = i.Quantity(total_quantity_value, unit)
    
    return inv_cli.create_sample(
        name=name,
        tags=tag_objects,
        description=description,
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
def list_samples(page_size: int = 20, order_by: str = "lastModified", sort_order: str = "desc") -> dict:
    """
    Lists samples in the inventory with pagination and sorting
    
    Usage: Browse sample collection, find recent additions
    Sorting: Options include "lastModified", "name", "created"
    Returns: Paginated list of sample metadata
    """
    pagination = i.Pagination(page_size=page_size, order_by=order_by, sort_order=sort_order)
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
    result = inv_cli.split_subsample(subsample_id, num_new_subsamples, quantity_per_subsample)
    return result.data if hasattr(result, 'data') else result


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
    parent_container_id: Union[int, str] = None
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
    parent_container_id: Union[int, str] = None
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
def get_container(container_id: Union[int, str], include_content: bool = False) -> dict:
    """
    Retrieves container information with optional content listing
    
    Usage: Examine container properties and optionally see what's inside
    Performance: Set include_content=False for faster queries on large containers
    Returns: Container details and optionally contained items
    """
    return inv_cli.get_container_by_id(container_id, include_content)


@mcp.tool(tags={"rspace", "inventory", "containers"})
def list_containers(page_size: int = 20) -> dict:
    """
    Lists top-level containers (not nested within other containers)
    
    Usage: Browse main container organization structure
    Returns: Paginated list of root-level containers
    """
    pagination = i.Pagination(page_size=page_size)
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
    return {"success": result.is_ok(), "results": result.data if hasattr(result, 'data') else str(result)}


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
    return {"success": result.is_ok(), "results": result.data if hasattr(result, 'data') else str(result)}


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
    return {"success": result.is_ok(), "results": result.data if hasattr(result, 'data') else str(result)}


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
    return {"success": result.is_ok(), "results": result.data if hasattr(result, 'data') else str(result)}


# ==================== TEMPLATE MANAGEMENT ====================
# Tools for creating and using sample templates for standardization

@mcp.tool(tags={"rspace", "inventory", "templates"})
def create_sample_template(template_data: dict) -> dict:
    """
    Creates a reusable template for sample creation
    
    Usage: Standardize sample creation with predefined fields and validation
    Template data: Define field structure, default values, and constraints
    Returns: Created template information for future sample generation
    """
    return inv_cli.create_sample_template(template_data)


@mcp.tool(tags={"rspace", "inventory", "templates"})
def get_sample_template(template_id: Union[int, str]) -> dict:
    """
    Retrieves detailed information about a sample template
    
    Usage: Examine template structure before using for sample creation
    Returns: Complete template definition including field specifications
    """
    return inv_cli.get_sample_template_by_id(template_id)


@mcp.tool(tags={"rspace", "inventory", "templates"})
def list_sample_templates(page_size: int = 20) -> dict:
    """
    Lists available sample templates for reuse
    
    Usage: Browse existing templates before creating new samples
    Returns: Paginated list of template metadata
    """
    pagination = i.Pagination(page_size=page_size)
    return inv_cli.list_sample_templates(pagination)


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
def add_extra_fields_to_item(item_id: Union[int, str], field_data: List[dict]) -> dict:
    """
    Adds custom metadata fields to inventory items
    
    Usage: Extend items with experiment-specific or project-specific data
    Field format: [{"name": "Field Name", "type": "text|number", "content": "value"}]
    Types: 'text' for strings, 'number' for numeric values
    
    Returns: Updated item with new custom fields
    """
    extra_fields = []
    for field in field_data:
        field_type = i.ExtraFieldType.TEXT if field.get('type', 'text').lower() == 'text' else i.ExtraFieldType.NUMBER
        ef = i.ExtraField(field['name'], field_type, field.get('content', ''))
        extra_fields.append(ef)
    
    return inv_cli.add_extra_fields(item_id, *extra_fields)


@mcp.tool(tags={"rspace", "inventory", "utility"})
def generate_barcode(global_id: str, barcode_type: str = "BARCODE") -> bytes:
    """
    Generates scannable barcodes for inventory items
    
    Usage: Create physical labels for sample tracking and identification
    Types: 'BARCODE' for standard linear barcodes, 'QR' for QR codes
    Returns: Binary barcode image data for printing or display
    """
    bc_type = i.Barcode.BARCODE if barcode_type.upper() == "BARCODE" else i.Barcode.QR
    return inv_cli.barcode(global_id, barcode_type=bc_type)


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
    Creates multiple samples efficiently in a single operation
    
    Usage: High-performance sample creation for large datasets
    Performance: Much faster than individual create_sample calls
    Format: List of sample definition dictionaries
    
    Note: Implementation should use batch API endpoints when available
    Returns: Results for all created samples with error handling
    """
    # TODO: Implement bulk creation logic
    # This would use batch endpoints or optimized iteration
    # depending on what the RSpace API supports
    pass


@mcp.tool(tags={"rspace", "inventory", "utility"})
def get_recent_samples_summary(days_back: int = 7, page_size: int = 10) -> list:
    """
    Retrieves recent samples with minimal data for dashboard views
    
    Usage: Quick overview of recent activity without full sample details
    Performance: Optimized for dashboard and summary displays
    Filtering: Configurable time window and result count
    
    Returns: Lightweight sample list with essential information only
    """
    # TODO: Implement efficient recent samples query
    # This would use date filtering and minimal field selection
    # for optimal performance
    pass


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