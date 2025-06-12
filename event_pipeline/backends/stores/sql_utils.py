import typing


def build_filter_params(filter_kwargs):
    conditions = []
    parameters = []

    for key, value in filter_kwargs.items():
        if '__' in key:
            field, operator = key.rsplit('__', 1)
            if operator == 'contains':
                conditions.append(f"{field} LIKE %s")
                parameters.append(f'%{value}%')
            elif operator == 'startswith':
                conditions.append(f"{field} LIKE %s")
                parameters.append(f'{value}%')
            elif operator == 'endswith':
                conditions.append(f"{field} LIKE %s")
                parameters.append(f'%{value}')
            elif operator in ('gt', 'gte', 'lt', 'lte'):
                op_map = {'gt': '>', 'gte': '>=', 'lt': '<', 'lte': '<='}
                conditions.append(f"{field} {op_map[operator]} %s")
                parameters.append(value)
        else:
            conditions.append(f"{key} = %s")
            parameters.append(value)
    return parameters, conditions


def map_types(field_type: typing.Any) -> str:
    from pydantic_mini.typing import get_type

    field_type = get_type(field_type)
    if field_type == bool:
        return "BOOLEAN"
    elif field_type == int:
        return "INTEGER"
    elif field_type == float:
        return "REAL"
    return "TEXT"
