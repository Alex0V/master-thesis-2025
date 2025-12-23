package com.example.recipeapp.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.recipeapp.data.api.RecipeApiService
import com.example.recipeapp.data.manager.TokenManager
import com.example.recipeapp.data.model.LogoutRequest
import com.example.recipeapp.data.model.RecipeSummary
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

class FeedViewModel(
    private val apiService: RecipeApiService
) : ViewModel() {

    // Стан завантаження
    private val _isLoading = MutableStateFlow(false)
    val isLoading = _isLoading.asStateFlow()

    // Стан помилки (якщо щось піде не так)
    private val _error = MutableStateFlow<String?>(null)
    val error = _error.asStateFlow()

    // Стан списку рецептів
    private val _recipes = MutableStateFlow<List<RecipeSummary>>(emptyList())
    val recipes = _recipes.asStateFlow()

    // 🚀 При створенні ViewModel одразу вантажимо рецепти
    init {
        loadRecommendations()
    }

    fun loadRecommendations() {
        viewModelScope.launch {
            _isLoading.value = true
            _error.value = null
            try {
                // Запит на сервер
                val loadedRecipes = apiService.getRecommendations()
                _recipes.value = loadedRecipes
            } catch (e: Exception) {
                _error.value = "Не вдалося завантажити рецепти: ${e.message}"
            } finally {
                _isLoading.value = false
            }
        }
    }

}