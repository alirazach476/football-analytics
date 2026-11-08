{% test non_negative(model, column_name) %}
select * from {{ model }} where {{ column_name }} < 0
{% endtest %}

{% test expression_is_true(model, expression) %}
select * from {{ model }} where not ({{ expression }})
{% endtest %}
