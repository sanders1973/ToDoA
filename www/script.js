
var shinyjs = {};

shinyjs.loadFromStorage = function() {
    var userData = localStorage.getItem('userData');
    if (userData) {
        Shiny.setInputValue('storage_data', userData);
    } else {
        Shiny.setInputValue('storage_data', '');
    }
}

shinyjs.saveToStorage = function(params) {
    localStorage.setItem('userData', params);
}
