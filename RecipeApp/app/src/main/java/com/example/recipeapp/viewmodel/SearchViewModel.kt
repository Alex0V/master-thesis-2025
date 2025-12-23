package com.example.recipeapp.viewmodel

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.recipeapp.data.api.RecipeApiService
import com.example.recipeapp.data.model.RecipeSummary
import com.example.recipeapp.data.model.TagGroupResponse
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

@OptIn(FlowPreview::class)
class SearchViewModel(private val apiService: RecipeApiService) : ViewModel() {

    // СТАНИ UI
    private val _searchQuery = MutableStateFlow("")
    val searchQuery = _searchQuery.asStateFlow()

    private val _tagGroups = MutableStateFlow<List<TagGroupResponse>>(emptyList())
    val tagGroups = _tagGroups.asStateFlow()

    // Вибраний тег: Pair("cuisine", "Italian") або null
    private val _selectedTag = MutableStateFlow<Pair<String, String>?>(null)
    val selectedTag = _selectedTag.asStateFlow()

    private val _searchResults = MutableStateFlow<List<RecipeSummary>>(emptyList())
    val searchResults = _searchResults.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading = _isLoading.asStateFlow()

    init {
        loadTags()
        setupSearchObserver()
    }

    private fun loadTags() {
        viewModelScope.launch {
            try {
                _tagGroups.value = apiService.getRecipeTags()
            } catch (e: Exception) {
                Log.e("SearchVM", "Error loading tags", e)
            }
        }
    }

    private fun setupSearchObserver() {
        viewModelScope.launch {
            // Об'єднуємо потоки тексту і тегу. Якщо змінюється хоч щось - запускаємо пошук.
            combine(_searchQuery, _selectedTag) { query, tag ->
                query to tag
            }
                .debounce(500L) // Чекаємо 500мс тиші перед запитом
                .collect { (query, tag) ->
                    // Робимо пошук, тільки якщо щось введено або вибрано тег
                    if (query.isNotBlank() || tag != null) {
                        performSearch(query, tag)
                    } else {
                        _searchResults.value = emptyList()
                    }
                }
        }
    }

    private suspend fun performSearch(query: String, tag: Pair<String, String>?) {
        _isLoading.value = true
        try {
            val results = apiService.searchRecipes(
                query = query.ifBlank { null },
                tagType = tag?.first,
                tagName = tag?.second
            )
            _searchResults.value = results
        } catch (e: Exception) {
            Log.e("SearchVM", "Search failed", e)
            _searchResults.value = emptyList()
        } finally {
            _isLoading.value = false
        }
    }

    // --- Public Methods для UI ---
    fun onQueryChange(newQuery: String) {
        _searchQuery.value = newQuery
    }

    fun onTagSelected(category: String, tag: String) {
        if (_selectedTag.value?.second == tag) {
            _selectedTag.value = null // Відмінити вибір
        } else {
            _selectedTag.value = category to tag
        }
    }

    fun clearSearch() {
        _searchQuery.value = ""
        _selectedTag.value = null
    }
}