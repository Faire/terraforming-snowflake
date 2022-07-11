
def parse_field(field, data_type_str):
    '''
    parses field values casting to the proper type. 
    type values can be ['String','Integer','Double','Long','Boolean','List']
        (the last one `List` would always be a list of strings).
    '''
    if data_type_str == 'String':
        newval = field
        if newval.startswith('[') and newval.endswith(']'):
            newval = newval[1:-1]
    elif data_type_str == 'Integer':
        newval = int(field) if field else None
    elif data_type_str == 'Double':
        newval = float(field) if field else None
    elif data_type_str == 'Long':
        newval = int(field) if field else None
    elif data_type_str == 'Boolean':
        newval = True if field.lower() == 'true' else False
    elif data_type_str == 'List':
        if field == '[]':
            newval = []
        else:
            newval = field[1:-1].split(', ')
    else:
        raise ValueError(f"Unrecognized type {data_type_str}")
    
    return newval


def stage_parser(data:list):
    '''expects pivot style data in the following format:
        [
            [parent_property:str, property_name:str, property_type:str, property_value:str, property_default:str],
            [parent_property:str, property_name:str, property_type:str, property_value:str, property_default:str],
            ...
        ]
    returns a dict of 
        {
            parent_property1: {
                property_name:property_value,
                property_name:property_value,
                ...
            } 
        }
    Also, if a value is the same as the default value, don't include it 
    0: parent_property
    1: property_name
    2: property_type
    3: property_value
    4: property_default
    '''
    data_dict = {}
    for row in data:
        if row[3] == row[4]:
            # property is default value, so skip
            continue
        else:
            if row[0] not in data_dict:
                data_dict[row[0]] = {}
            data_dict[row[0]][row[1]] = parse_field(row[3], row[2])
    return data_dict
