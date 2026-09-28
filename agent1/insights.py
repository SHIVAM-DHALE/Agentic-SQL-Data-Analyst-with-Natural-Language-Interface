"""
insights.py
Generate analyst-style business insights using:
1. User question
2. SQL result columns
3. SQL result rows
"""

from decimal import Decimal


def _is_number(value):
    return isinstance(value, (int, float, Decimal))


def _format_money(value):
    return f"₹{float(value):,.2f}"


def _format_number(value):
    return f"{float(value):,.2f}"


def _best_label_column(columns):
    priority_columns = [
        "product_name",
        "category",
        "customer_name",
        "country",
        "status",
        "customer_id",
        "product_id",
        "order_id"
    ]

    lower_columns = [col.lower() for col in columns]

    for col in priority_columns:
        if col in lower_columns:
            return lower_columns.index(col)

    return 0


def _best_numeric_column(columns, row):
    priority_keywords = [
        "revenue",
        "sales",
        "amount",
        "total",
        "quantity",
        "price",
        "count",
        "avg",
        "average"
    ]

    lower_columns = [col.lower() for col in columns]

    for keyword in priority_keywords:
        for i, col in enumerate(lower_columns):
            if keyword in col and _is_number(row[i]):
                return i

    for i, value in enumerate(row):
        if _is_number(value):
            return i

    return None


def generate_insights(question, columns, data):
    if not data:
        return "Business Summary\nNo records were found for this query."

    question = question.lower()

    try:
        # --------------------------
        # Single value result
        # Example: [(1000,)]
        # --------------------------
        if len(columns) == 1:
            value = data[0][0]
            col = columns[0].lower()

            if "count" in col or "count" in question or "total" in question:
                if "customer" in question:
                    meaning = f"There are {value} customers in the database."
                elif "product" in question:
                    meaning = f"There are {value} products in the database."
                elif "order" in question or "sale" in question:
                    meaning = f"There are {value} orders/sales records in the database."
                else:
                    meaning = f"The total count is {value}."

                return (
                    "Business Summary\n"
                    "────────────────────────\n"
                    f"• Result : {meaning}\n"
                    "• Interpretation : This gives a quick overview of the dataset size."
                )

            if "avg" in col or "average" in col or "average" in question:
                return (
                    "Business Summary\n"
                    "────────────────────────\n"
                    f"• Average Value : {_format_number(value)}\n"
                    "• Interpretation : This represents the central tendency for the selected metric."
                )

            if "sum" in col or "revenue" in col or "amount" in col:
                return (
                    "Business Summary\n"
                    "────────────────────────\n"
                    f"• Total Value : {_format_money(value)}\n"
                    "• Interpretation : This is the combined value for the selected business metric."
                )

            if "max" in col or "maximum" in question or "highest" in question:
                return (
                    "Business Summary\n"
                    "────────────────────────\n"
                    f"• Highest Value : {_format_number(value)}\n"
                    "• Interpretation : This is the maximum value found for the requested metric."
                )

            if "min" in col or "minimum" in question or "lowest" in question:
                return (
                    "Business Summary\n"
                    "────────────────────────\n"
                    f"• Lowest Value : {_format_number(value)}\n"
                    "• Interpretation : This is the minimum value found for the requested metric."
                )

            return (
                "Business Summary\n"
                "────────────────────────\n"
                f"• Returned Value : {value}"
            )

        # --------------------------
        # One row result
        # Example: second highest product
        # --------------------------
        if len(data) == 1:
            row = data[0]

            label_index = _best_label_column(columns)
            numeric_index = _best_numeric_column(columns, row)

            label = row[label_index]

            if numeric_index is not None:
                metric_name = columns[numeric_index]
                metric_value = row[numeric_index]

                return (
                    "Business Summary\n"
                    "────────────────────────\n"
                    f"• Matching Record : {label}\n"
                    f"• {metric_name} : {_format_money(metric_value) if 'revenue' in metric_name.lower() or 'amount' in metric_name.lower() or 'sales' in metric_name.lower() else metric_value}\n"
                    "• Interpretation : This record is the most relevant match for the user's question."
                )

            details = ", ".join(
                f"{col}: {val}" for col, val in zip(columns, row)
            )

            return (
                "Business Summary\n"
                "────────────────────────\n"
                f"• Matching Record : {details}"
            )

        # --------------------------
        # Multi-row result
        # --------------------------
        label_index = _best_label_column(columns)
        numeric_index = _best_numeric_column(columns, data[0])

        if numeric_index is None:
            return (
                "Business Summary\n"
                "────────────────────────\n"
                f"• Records Analysed : {len(data)}\n"
                "• Interpretation : The query returned non-numeric records for review."
            )

        numeric_name = columns[numeric_index]
        label_name = columns[label_index]

        total = 0
        highest = None
        lowest = None

        for row in data:
            value = float(row[numeric_index])
            label = row[label_index]

            total += value

            if highest is None or value > highest[1]:
                highest = (label, value)

            if lowest is None or value < lowest[1]:
                lowest = (label, value)

        average = total / len(data)

        money_metric = any(
            word in numeric_name.lower()
            for word in ["revenue", "sales", "amount", "price"]
        )

        total_display = _format_money(total) if money_metric else _format_number(total)
        highest_display = _format_money(highest[1]) if money_metric else _format_number(highest[1])
        lowest_display = _format_money(lowest[1]) if money_metric else _format_number(lowest[1])
        average_display = _format_money(average) if money_metric else _format_number(average)

        recommendation = "Focus on the top-performing segment and investigate the lowest-performing segment for improvement opportunities."

        if "category" in question or "category" in label_name.lower():
            recommendation = "The highest-performing category should be prioritised, while the lowest category may need better pricing, promotion, or inventory strategy."

        if "product" in question or "product" in label_name.lower():
            recommendation = "The best-performing product can be promoted further, while low-performing products should be reviewed for demand or pricing issues."

        if "customer" in question or "customer" in label_name.lower():
            recommendation = "High-value customers can be targeted for loyalty programs, while lower-value segments may need engagement campaigns."

        return (
            "Business Summary\n"
            "────────────────────────\n"
            f"• Records Analysed : {len(data)}\n"
            f"• Total {numeric_name} : {total_display}\n"
            f"• Best Performing {label_name} : {highest[0]} generated {highest_display}\n"
            f"• Lowest Performing {label_name} : {lowest[0]} generated {lowest_display}\n"
            f"• Average {numeric_name} : {average_display}\n"
            f"• Recommendation : {recommendation}"
        )

    except Exception as e:
        return f"Unable to generate insights: {e}"
