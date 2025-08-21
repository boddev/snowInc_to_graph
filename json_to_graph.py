#!/usr/bin/env python3
"""
Convert JSON data to Microsoft Graph externalItem sch        return "string"  # Default fallback
    
    def determine_labels(self, name, value):.

This script analyzes a JSON object and generates a Microsoft Graph externalItem schema
that can be used to register external content with Microsoft Search.

Based on documentation:
https://learn.microsoft.com/en-us/graph/api/externalconnectors-externalconnection-patch-schema
"""

import json
import re
from datetime import datetime


class GraphSchemaGenerator:
    """Generates Microsoft Graph externalItem schemas from JSON data."""
    
    def __init__(self):
        self.datetime_patterns = [
            r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$',  # YYYY-MM-DD HH:MM:SS
            r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',   # ISO format (with optional timezone)
            r'^\d{4}-\d{2}-\d{2}$',                     # YYYY-MM-DD
            r'^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}$',  # YYYY/MM/DD HH:MM:SS
            r'^\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}$',  # MM/DD/YYYY HH:MM:SS
            r'^\d{4}/\d{2}/\d{2}$',                     # YYYY/MM/DD
            r'^\d{2}/\d{2}/\d{4}$',                     # MM/DD/YYYY
        ]
    
    def sanitize_property_name(self, name):
        """
        Sanitize property name according to Microsoft Graph requirements.
        Maximum 32 characters, only alphanumeric characters allowed.
        Converts to camelCase format.
        """
        # Split on non-alphanumeric characters to get words
        words = re.findall(r'[a-zA-Z0-9]+', name)
        
        if not words:
            return 'property'
        
        # Convert to camelCase: first word lowercase, subsequent words capitalized
        camel_case = words[0].lower()
        for word in words[1:]:
            camel_case += word.capitalize()
        
        # Limit length to 32 characters
        camel_case = camel_case[:32]
        
        # Ensure it starts with a letter
        if camel_case and not camel_case[0].isalpha():
            camel_case = 'prop' + camel_case.capitalize()
            camel_case = camel_case[:32]
        
        return camel_case or 'property'
    
    def detect_property_type(self, value):
        """Detect the Microsoft Graph property type based on the value."""
        if value is None or value == "":
            return "string"  # Default to string for empty/null values
        
        if isinstance(value, bool):
            return "boolean"
        
        if isinstance(value, str):
            # Check if it looks like a datetime
            for pattern in self.datetime_patterns:
                if re.match(pattern, value):
                    return "dateTime"
            
            # Check if it's a numeric string
            if value.isdigit():
                return "int64"
            
            try:
                float(value)
                return "double"
            except ValueError:
                pass
            
            return "string"
        
        if isinstance(value, int):
            return "int64"
        
        if isinstance(value, float):
            return "double"
        
        if isinstance(value, dict):
            # For objects with link/value structure, treat as string
            return "string"
        
        if isinstance(value, list):
            return "stringCollection"
        
        return "string"  # Default fallback
    
    def determine_labels(self, name, value, property_type):
        """Determine appropriate labels for the property based on name, value, and type."""
        labels = []
        
        name_lower = name.lower()
        
        # Title-like fields - be selective to avoid duplicates, prefer short_description
        if name_lower == 'short_description' or name_lower == 'shortdescription':
            labels.append("title")
        elif name_lower in ['title', 'subject'] and 'short' not in name_lower:
            labels.append("title")
        
        # URL fields
        if 'url' in name_lower or 'link' in name_lower:
            labels.append("url")
        
        # Creator/author fields (only for string types)
        if property_type == "string" and any(keyword in name_lower for keyword in ['created_by', 'createdby', 'author', 'opener']):
            labels.append("createdBy")
        
        # Modifier fields (only for string types)
        if property_type == "string" and any(keyword in name_lower for keyword in ['updated_by', 'updatedby', 'modified_by', 'resolver']):
            labels.append("lastModifiedBy")
        
        # DateTime fields (only for dateTime types) - be more selective to avoid duplicates
        # Prefer sys_ fields over other fields for standard labels
        if property_type == "dateTime":
            # Only assign createdDateTime to the most standard creation field
            if name_lower == 'sys_created_on' or name_lower == 'syscreatedon':
                labels.append("createdDateTime")
            # Only assign lastModifiedDateTime to the most standard modification field  
            elif name_lower == 'sys_updated_on' or name_lower == 'sysupdatedon':
                labels.append("lastModifiedDateTime")
        
        return labels
    
    def process_complex_value(self, value):
        """Process complex objects (like those with 'link' and 'value' properties)."""
        if isinstance(value, dict):
            if 'value' in value:
                return str(value['value'])
            elif 'link' in value:
                return str(value['link'])
            else:
                # Convert dict to JSON string
                return json.dumps(value)
        return str(value)
    
    def create_property_definition(self, name, value):
        """Create a property definition for the schema."""
        sanitized_name = self.sanitize_property_name(name)
        property_type = self.detect_property_type(value)
        labels = self.determine_labels(name, value, property_type)
        
        prop_def = {
            "name": sanitized_name,
            "type": property_type,
            "isRetrievable": True,  # Generally useful for most properties
        }
        
        # Set searchable only for string types
        if property_type in ["string", "stringCollection"]:
            prop_def["isSearchable"] = True
        
        # Set queryable for commonly queried fields
        is_queryable = any(keyword in name.lower() for keyword in ['number', 'id', 'state', 'status', 'priority', 'category', 'type'])
        
        # Add refinable for categorical data - refinable properties must also be queryable
        is_refinable = any(keyword in name.lower() for keyword in ['category', 'state', 'status', 'priority', 'type', 'group'])
        
        if is_queryable or is_refinable:
            prop_def["isQueryable"] = True
            
        if is_refinable:
            prop_def["isRefinable"] = True
        
        # Add labels if any were determined
        if labels:
            prop_def["labels"] = labels
        
        return prop_def
    
    def generate_schema(self, json_data):
        """Generate the complete Microsoft Graph externalItem schema."""
        properties = []
        
        for key, value in json_data.items():
            # Skip complex nested objects for now, but process simple link/value objects
            if isinstance(value, dict) and ('link' in value or 'value' in value):
                # Create a property for the value part
                processed_value = self.process_complex_value(value)
                prop_def = self.create_property_definition(key, processed_value)
            else:
                prop_def = self.create_property_definition(key, value)
            
            properties.append(prop_def)
        
        schema = {
            "baseType": "microsoft.graph.externalItem",
            "properties": properties
        }
        
        return schema

    def convert_to_external_item(self, json_data, connection_id="servicenow-incidents"):
        """Convert JSON data to Microsoft Graph externalItem format."""
        
        # Generate a unique ID for the item (using sys_id if available, otherwise number)
        item_id = json_data.get('sys_id', json_data.get('number', 'unknown'))
        if not item_id:
            hash_value = hash(str(json_data)) % 1000000
            item_id = "incident_" + str(hash_value)
        
        # Create the properties object based on the schema
        properties = {}
        
        for key, value in json_data.items():
            # Get the sanitized property name (same as used in schema)
            sanitized_name = self.sanitize_property_name(key)
            
            # Process the value based on its type
            if isinstance(value, dict) and ('link' in value or 'value' in value):
                # Handle complex objects with link/value structure
                processed_value = self.process_complex_value(value)
            else:
                processed_value = self._format_value_for_external_item(value)
            
            properties[sanitized_name] = processed_value
        
        # Create content for full-text search (combine key fields)
        content_parts = []
        content_fields = ['number', 'short_description', 'description', 'comments', 'work_notes']
        
        for field in content_fields:
            if field in json_data and json_data[field]:
                if isinstance(json_data[field], str) and json_data[field].strip():
                    content_parts.append(json_data[field].strip())
        
        content_text = ' '.join(content_parts) if content_parts else f"ServiceNow Incident {item_id}"
        
        # Create the externalItem
        external_item = {
            "id": str(item_id),
            "properties": properties,
            "content": {
                "type": "text",
                "value": content_text
            },
            "acl": [
                {
                    "type": "everyone",
                    "value": "everyone",
                    "accessType": "grant"
                }
            ]
        }
        
        return external_item
    
    def _format_value_for_external_item(self, value):
        """Format a value appropriately for externalItem properties."""
        if value is None:
            return None
        elif value == "":
            return None  # Don't include empty strings
        elif isinstance(value, bool):
            return value
        elif isinstance(value, (int, float)):
            return value
        elif isinstance(value, str):
            # For datetime strings, keep them as strings (Graph will parse them)
            return value
        elif isinstance(value, list):
            # Convert list to string array, filtering out empty values
            return [str(item) for item in value if item is not None and str(item).strip()]
        else:
            return str(value)


def main():
    """Main function to demonstrate the schema generation and external item creation."""
    
    # Sample ServiceNow incident data
    sample_data = {
        "rfc": "",
        "cause": "",
        "order": "",
        "state": "7",
        "active": "false",
        "impact": "1",
        "notify": "1",
        "number": "INC0000001",
        "parent": "",
        "skills": "",
        "sys_id": "9c573169c611228700193229fff72400",
        "cmdb_ci": {
            "link": "https://xxxxxx.service-now.com/api/now/table/cmdb_ci/b0c4030ac0a800090152e7a4564ca36c",
            "value": "b0c4030ac0a800090152e7a4564ca36c"
        },
        "company": "",
        "sla_due": "",
        "urgency": "1",
        "approval": "",
        "category": "network",
        "comments": "",
        "contract": "",
        "due_date": "",
        "location": {
            "link": "https://xxxxxx.service-now.com/api/now/table/cmn_location/1083361cc611227501b682158cabf646",
            "value": "1083361cc611227501b682158cabf646"
        },
        "made_sla": "false",
        "priority": "1",
        "severity": "1",
        "sys_tags": "",
        "work_end": "",
        "caller_id": "",
        "caused_by": "",
        "closed_at": "2014-12-10 23:10:06",
        "closed_by": {
            "link": "https://xxxxxx.service-now.com/api/now/table/sys_user/9ee1b13dc6112271007f9d0efdb69cd0",
            "value": "9ee1b13dc6112271007f9d0efdb69cd0"
        },
        "follow_up": "",
        "knowledge": "false",
        "opened_at": "2014-12-09 23:09:51",
        "opened_by": {
            "link": "https://xxxxxx.service-now.com/api/now/table/sys_user/681ccaf9c0a8016400b98a06818d57c7",
            "value": "681ccaf9c0a8016400b98a06818d57c7"
        },
        "origin_id": "",
        "close_code": "Closed/Resolved by Caller",
        "escalation": "0",
        "group_list": "",
        "problem_id": {
            "link": "https://xxxxxx.service-now.com/api/now/table/problem/9d3a266ac6112287004e37fb2ceb0133",
            "value": "9d3a266ac6112287004e37fb2ceb0133"
        },
        "sys_domain": {
            "link": "https://xxxxxx.service-now.com/api/now/table/sys_user_group/global",
            "value": "global"
        },
        "user_input": "",
        "watch_list": "",
        "work_notes": "",
        "work_start": "",
        "assigned_to": {
            "link": "https://xxxxxx.service-now.com/api/now/table/sys_user/46b87022a9fe198101a78787e40d7547",
            "value": "46b87022a9fe198101a78787e40d7547"
        },
        "close_notes": "Closed before close notes were made mandatory",
        "description": "User can't access email on mail.company.com.",
        "reopened_by": "",
        "resolved_at": "2015-03-11 19:56:12",
        "resolved_by": {
            "link": "https://xxxxxx.service-now.com/api/now/table/sys_user/6816f79cc0a8016401c5a33be04be441",
            "value": "6816f79cc0a8016401c5a33be04be441"
        },
        "subcategory": "",
        "time_worked": "",
        "upon_reject": "",
        "activity_due": "",
        "approval_set": "",
        "business_stc": "1892781",
        "calendar_stc": "7937181",
        "contact_type": "",
        "origin_table": "",
        "reopen_count": "",
        "route_reason": "",
        "delivery_plan": "",
        "delivery_task": "",
        "reopened_time": "",
        "sys_mod_count": "22",
        "upon_approval": "",
        "correlation_id": "",
        "expected_start": "",
        "incident_state": "7",
        "sys_class_name": "incident",
        "sys_created_by": "pat",
        "sys_created_on": "2013-07-10 18:24:13",
        "sys_updated_by": "kgoldstein",
        "sys_updated_on": "2021-02-26 00:53:54",
        "business_impact": "",
        "child_incidents": "",
        "parent_incident": "",
        "sys_domain_path": "/",
        "work_notes_list": "",
        "approval_history": "",
        "assignment_group": {
            "link": "https://xxxxxx.service-now.com/api/now/table/sys_user_group/d625dccec0a8016700a222a0f7900d06",
            "value": "d625dccec0a8016700a222a0f7900d06"
        },
        "business_service": "",
        "service_offering": "",
        "business_duration": "1970-01-22 21:46:21",
        "calendar_duration": "1970-04-02 20:46:21",
        "short_description": "Can't read email",
        "universal_request": "",
        "reassignment_count": "1",
        "correlation_display": "",
        "task_effective_number": "INC0000001",
        "comments_and_work_notes": "",
        "additional_assignee_list": "",
        "x_mioms_azure_moni_alertid": "",
        "x_mioms_azure_moni_alertrule": "",
        "x_mo365_o365_incid_testfield": "",
        "x_mioms_azure_moni_signaltype": "",
        "x_mioms_azure_moni_alertcontext": "",
        "x_mioms_azure_moni_subscription": "",
        "x_mioms_azure_moni_alertseverity": "",
        "x_mioms_azure_moni_fireddatetime": "",
        "x_mioms_azure_moni_originalertid": "",
        "x_mioms_azure_moni_alerttargetids": "",
        "x_mioms_azure_moni_monitorservice": "",
        "x_mioms_azure_moni_monitorcondition": "",
        "x_mioms_azure_moni_resolveddatetime": ""
    }
    
    # Generate the schema and external item
    generator = GraphSchemaGenerator()
    
    print("=" * 60)
    print("GENERATING MICROSOFT GRAPH SCHEMA")
    print("=" * 60)
    schema = generator.generate_schema(sample_data)
    
    # Output the schema as formatted JSON
    print("Microsoft Graph externalItem Schema:")
    print("=" * 50)
    print(json.dumps(schema, indent=2))
    
    # Save schema to file
    with open('servicenow_incident_schema.json', 'w') as f:
        json.dump(schema, f, indent=2)
    
    print(f"\nSchema saved to 'servicenow_incident_schema.json'")
    print(f"Total properties: {len(schema['properties'])}")
    
    print("\n" + "=" * 60)
    print("GENERATING EXTERNAL ITEM")
    print("=" * 60)
    
    # Generate the external item
    external_item = generator.convert_to_external_item(sample_data)
    
    # Output the external item as formatted JSON
    print("Microsoft Graph externalItem:")
    print("=" * 50)
    print(json.dumps(external_item, indent=2))
    
    # Save external item to file
    with open('servicenow_incident_external_item.json', 'w') as f:
        json.dump(external_item, f, indent=2)
    
    print(f"\nExternal item saved to 'servicenow_incident_external_item.json'")
    print(f"Item ID: {external_item['id']}")
    print(f"Total properties: {len(external_item['properties'])}")
    print(f"Content length: {len(external_item['content']['value'])} characters")


if __name__ == "__main__":
    main()
