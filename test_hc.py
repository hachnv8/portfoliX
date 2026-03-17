import json
import streamlit.components.v1 as components

categories = ["17/03/2026"]
data = [-2.27]

html = f"""
<!DOCTYPE html>
<html>
<head>
    <script src="https://code.highcharts.com/highcharts.js"></script>
</head>
<body>
<div id="container" style="width:100%; height:300px;"></div>
<script>
    document.addEventListener("DOMContentLoaded", function() {{
        Highcharts.chart('container', {{
            chart: {{
                type: 'areaspline',
                backgroundColor: 'transparent'
            }},
            title: {{ text: null }},
            xAxis: {{
                categories: {json.dumps(categories)},
                labels: {{ style: {{ color: '#aaaaaa' }} }},
                gridLineColor: '#333333'
            }},
            yAxis: {{
                title: {{ text: null }},
                labels: {{ format: '{{value}}%', style: {{ color: '#aaaaaa' }} }},
                gridLineColor: '#333333'
            }},
            legend: {{ enabled: false }},
            credits: {{ enabled: false }},
            tooltip: {{
                pointFormat: '<b>{{point.y}}%</b>'
            }},
            plotOptions: {{
                areaspline: {{
                    fillOpacity: 0.2,
                    color: '#00ff00',
                    marker: {{ enabled: true, radius: 4 }}
                }}
            }},
            series: [{{
                name: 'Lãi/Lỗ',
                data: {json.dumps(data)}
            }}]
        }});
    }});
</script>
</body>
</html>
"""
with open("test.html", "w") as f:
    f.write(html)
