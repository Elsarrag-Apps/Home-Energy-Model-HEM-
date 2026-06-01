from graphlib import CycleError, TopologicalSorter


def build_preheated_water_source_dependency_graph(
    preheated_sources_dict: dict,
) -> dict[str, set[str]]:
    """
    Build a dependency graph for PreHeatedWaterSource objects.

    Returns a dictionary in the format expected by TopologicalSorter:
    - Keys are node names (PreHeatedWaterSource names)
    - Values are sets of predecessor nodes (nodes that must come before this node)

    Args:
        preheated_sources_dict: Dictionary of PreHeatedWaterSource configurations

    Returns:
        Dictionary mapping each source name to its set of PreHeatedWaterSource predecessors
    """
    graph = {}

    for name, data in preheated_sources_dict.items():
        cold_source_name = data.get("ColdWaterSource")
        predecessors = set()

        if cold_source_name in preheated_sources_dict:
            predecessors.add(cold_source_name)

        graph[name] = predecessors

    return graph


def topological_sort_preheated_water_sources(
    dependency_graph: dict[str, set[str]],
) -> list[str]:
    """
    Perform topological sort on PreHeatedWaterSource objects using graphlib.TopologicalSorter.

    Returns a list of source names in initialization order (dependencies first).

    Args:
        dependency_graph: Dictionary mapping source name to its set of PreHeatedWaterSource predecessors

    Returns:
        List of source names in topological order

    Raises:
        ValueError: If circular dependencies are detected (wraps CycleError from TopologicalSorter)
    """
    try:
        sorter = TopologicalSorter(dependency_graph)
        return list(sorter.static_order())
    except CycleError as err:
        raise ValueError(f"Circular dependency detected in PreHeatedWaterSource: {err}") from err
