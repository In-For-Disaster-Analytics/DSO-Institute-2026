"""Network visualization helpers."""

from __future__ import annotations

import networkx as nx
import plotly.graph_objects as go


def create_network_figure(
    science_backbone: dict[str, list[str]],
    topic_mappings: list[dict[str, object]],
    case_study_name: str,
) -> tuple[nx.Graph, go.Figure]:
    graph = nx.Graph()
    for domain in science_backbone:
        graph.add_node(domain, node_type="domain")
    for domain, subs in science_backbone.items():
        for sub in subs:
            graph.add_node(sub, node_type="subdiscipline")
            graph.add_edge(domain, sub)
    for mapping in topic_mappings:
        topic = mapping.get("topic_label") or mapping["topic"]
        graph.add_node(topic, node_type="topic")
        graph.add_edge(mapping["primary_domain"], topic)

    pos = nx.spring_layout(graph, k=2, iterations=50, seed=42)

    edge_trace = go.Scatter(
        x=[],
        y=[],
        line=dict(width=0.5, color="#888"),
        hoverinfo="none",
        mode="lines",
    )
    for edge in graph.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_trace["x"] += (x0, x1, None)
        edge_trace["y"] += (y0, y1, None)

    colors = {"domain": "#FF6B6B", "subdiscipline": "#4ECDC4", "topic": "#FFE66D"}
    sizes = {"domain": 20, "subdiscipline": 15, "topic": 12}

    node_traces = []
    for node_type in ["domain", "subdiscipline", "topic"]:
        nodes = [n for n, data in graph.nodes(data=True) if data.get("node_type") == node_type]
        node_traces.append(
            go.Scatter(
                x=[pos[n][0] for n in nodes],
                y=[pos[n][1] for n in nodes],
                mode="markers+text",
                text=nodes,
                textposition="top center",
                marker=dict(size=sizes[node_type], color=colors[node_type]),
                name=node_type.title(),
            )
        )

    fig = go.Figure(
        data=[edge_trace] + node_traces,
        layout=go.Layout(
            title=f"Science Backbone Network with Topics ({case_study_name})",
            showlegend=True,
            hovermode="closest",
            margin=dict(b=20, l=5, r=5, t=40),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            height=600,
        ),
    )
    return graph, fig

