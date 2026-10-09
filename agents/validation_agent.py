from schemas.report_schema import EnvironmentalReportData

def validate_report(data: EnvironmentalReportData, document_texts: dict[str, str]) -> EnvironmentalReportData:
    warnings = list(data.validation_warnings)
    gaps = list(data.data_gaps)

    expected = {
        "energy": "Energy records",
        "water": "Water records",
        "emissions": "Emission records",
        "waste": "Waste records",
        "clearances": "Environmental clearances and assessments",
        "compliance": "Environmental compliance records",
    }
    category_map = {
        "energy": data.energy_metrics,
        "water": data.water_metrics,
        "emissions": data.emissions_metrics,
        "waste": data.waste_metrics,
        "clearances": data.clearances_assessments,
        "compliance": data.compliance_metrics,
    }

    for key, label in expected.items():
        if not any(key in name.lower() for name in document_texts):
            warnings.append(f"Could not identify a source filename for {label}.")
        if not category_map[key]:
            gaps.append(f"No structured metrics extracted for {label}; manual review is required.")

    all_metrics = (
        data.energy_metrics + data.water_metrics + data.emissions_metrics +
        data.waste_metrics + data.clearances_assessments + data.compliance_metrics
    )
    for metric in all_metrics:
        if metric.value is None and metric.status in {"reported", "calculated"}:
            warnings.append(
                f"Metric '{metric.name}' is marked {metric.status} but has no value."
            )
        if metric.status == "not_applicable" and not (metric.notes or "").strip():
            warnings.append(
                f"Metric '{metric.name}' is marked not_applicable without a rationale."
            )

    data.validation_warnings = sorted(set(warnings))
    data.data_gaps = sorted(set(gaps))
    return data
