const socket = io('http://localhost:5000');

var next_rewrite_id = 0;

function get_original_query_field() {
    return document.getElementById('query-input');
}

function setQuery(source) {
    const queryField = get_original_query_field();
    if (source.value === 'custom') {
        queryField.classList.remove('disabled');
        return;
    }
    queryField.value = source.value;
    queryField.classList.add('disabled');
}

function run_rewriter() {
    socket.emit('run_rewriter', compose_rewrite_task());
}

function get_dataset() {
    return document.querySelector('input[name="dataset-select"]:checked').value;
}

function get_original_query() {
    return get_original_query_field().value;
}

function scroll_to_rewriter_settings() {
    document.getElementById('rewriter')
            .scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function notify_original_query_selected() {
    const dataset = get_dataset();
    const query = get_original_query();
    socket.emit('original_query_selected', { 'dataset': dataset, 'query': query });
    await new Promise(resolve => setTimeout(resolve, 10));
    scroll_to_rewriter_settings();
}

function compose_rewrite_task() {
    const scenario = document.querySelector('input[name="scenario-select"]:checked').value;
    const dataset = get_dataset();
    const query = get_original_query();
    const schema_deletions = (scenario === 'missing-data') ? gather_schema_deletions(dataset) : { 'tables': [], 'columns': [] };
    const rewriter_settings = gather_rewriter_settings();

    id = next_rewrite_id;
    next_rewrite_id += 1;

    return {
        'id': id,
        'dataset': dataset,
        'query': query,
        'deletions': schema_deletions,
        'settings': rewriter_settings
    };
}

function gather_schema_deletions(dataset_name) {
    const tableNames = Array.from(document.querySelectorAll(`input.table-deleter[data-dataset="${dataset_name}"]:checked`))
        .map(checkbox => parseInt(checkbox.dataset.tableId));
    const columnNames = Array.from(document.querySelectorAll(`input.column-deleter[data-dataset="${dataset_name}"]:checked`))
        .map(checkbox => {
            return {
                'table': parseInt(checkbox.dataset.tableId),
                'column': parseInt(checkbox.dataset.columnId)
            }
        })
        .filter(column => !tableNames.includes(column.table)); // If the whole table is deleted, we don't need to specify the column
    return { 'tables': tableNames, 'columns': columnNames };
}

function gather_rewriter_settings() {
    // General settings
    const table_filter = document.querySelector('select[name="table-filter"]').value;
    const rewriter = document.querySelector('select[name="rewriter"]').value;
    const ranker = document.querySelector('select[name="ranker"]').value;
    const intent_similarity = document.querySelector('select[name="similarity"]').value;

    // Detail settings
    const model = document.querySelector('select[name="gpt-model"]').value;
    const alternativeQueries = document.querySelector('input[name="alternative-query-count"]').value;
    const additionalQueries = document.querySelector('input[name="additional-query-count"]').value;
    const embeddingThreshold = document.querySelector('input[name="embedding-threshold"]').value;
    const sllmSelectivity = document.querySelector('input[name="sllm-expected-selectivity"]').value;
    const cllmThreshold = document.querySelector('input[name="cllm-threshold"]').value;
    const mmrLambda = document.querySelector('input[name="mmr-lambda"]').value;
    const lmmsPackageSize = document.querySelector('input[name="lmms-package-size"]').value;
    const correctionTries = document.querySelector('input[name="correction-tries"]').value;

    return {
        'table_filter': parseInt(table_filter),
        'rewriter': parseInt(rewriter),
        'ranker': parseInt(ranker),
        'intent_similarity': parseInt(intent_similarity),
        'model': model,
        'alternativeQueries': parseInt(alternativeQueries),
        'additionalQueries': parseInt(additionalQueries),
        'embeddingThreshold': parseFloat(embeddingThreshold),
        'sllmSelectivity': parseFloat(sllmSelectivity),
        'cllmThreshold': parseFloat(cllmThreshold),
        'mmrLambda': parseFloat(mmrLambda),
        'lmmsPackageSize': parseInt(lmmsPackageSize),
        'correctionTries': parseInt(correctionTries)
    };
}

socket.on('rewriter_started', function(status_info) {
    const marker = document.getElementById('rewrite-marker');
    marker.insertAdjacentHTML('beforebegin', status_info);
    marker.previousSibling.scrollIntoView({ behavior: 'smooth', block: 'center' });
});

socket.on('phase_done', function(phase_info) {
    document
        .getElementById(`${phase_info.phase}-status-${phase_info.rewrite_id}`)
        .innerHTML = phase_info.status;
});

socket.on('query_result', function(result) {
    document
        .getElementById('result-list')
        .insertAdjacentHTML('beforeend', result['content']);
    toggleQueryVisibility(result['rewrite_id'], result['query_id']);
    if (result['query_id'] === 'original') {
        document.getElementById('result-display-form').style.display = 'block';
        scroll_to_rewriter_settings();
    }
});

function toggleQueryVisibility(rewriteId, queryId) {
    const checkbox = document.querySelector(`input[data-rewrite-id="${rewriteId}"][data-query-id="${queryId}"]`);
    const query = document.querySelector(`.result[data-rewrite-id="${rewriteId}"][data-query-id="${queryId}"]`);
    if (checkbox.checked) {
        query.style.display = 'block';
    } else {
        query.style.display = 'none';
    }
}
