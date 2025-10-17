// общий помощник для Kendo UI / React / Angular
window.kendoToFastapiQuery = function(state) {
  const params = new URLSearchParams();

  // пагинация
  if (typeof state.skip === 'number' && typeof state.limit === 'number') {
    params.set('skip', String(state.skip));
    params.set('limit', String(state.limit));
  }

  // сортировка
  if (Array.isArray(state.sort) && state.sort.length) {
    // fastapi-filter обычно ожидает что-то вроде ?ordering=field или -field
    // возьмем первый (или соберите список)
    const s = state.sort[0];
    params.set('order_by', (s.dir === 'desc' ? '-' : '') + s.field);
  }

  const opMap = {
    eq: '',            // name=...
    neq: '__neq',
    contains: '__ilike',
    doesnotcontain: '__not_ilike', // придётся поддержать на бэке
    startswith: '__istartswith',
    endswith: '__iendswith',
    gt: '__gt',
    gte: '__ge',
    lt: '__lt',
    lte: '__le',
    in: '__in',
    isnull: '__isnull',
    isnotnull: '__isnull', // со значением false
  };

  function addFilter(f) {
    const { field, operator, value } = f;

    if (operator === 'isnull') {
      params.append(`${field}${opMap[operator]}`, 'true');
      return;
    }
    if (operator === 'isnotnull') {
      params.append(`${field}${opMap[operator]}`, 'false');
      return;
    }

    const suffix = opMap[operator] ?? '';
    if (operator === 'in' && Array.isArray(value)) {
      params.append(`${field}${suffix}`, value.join(','));
    } else {
      params.append(`${field}${suffix}`, String(value));
    }
  }

  function walk(node, logic = 'and') {
    // fastapi-filter не понимает вложенные OR из коробки,
    // поэтому:
    // - для logic='and' просто добавляем все условия
    // - для logic='or' — либо игнорируем (превратим в and),
    //   либо отправляем кастомный параметр, если у вас есть обработчик.
    if (Array.isArray(node?.filters)) {
      node.filters.forEach((f) => {
        if (f.filters) {
          walk(f, node.logic || logic);
        } else {
          addFilter(f);
        }
      });
    }
  }
  if (state.filter) {
    walk(state.filter);
  }

  console.log(params);

  return params;
}