package com.example.recipeapp.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.recipeapp.data.api.RecipeApiService
import com.example.recipeapp.data.model.RecipeSummary
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class FavoritesViewModel(
    private val apiService: RecipeApiService
) : ViewModel() {

    private val _recipes = MutableStateFlow<List<RecipeSummary>>(emptyList())
    val recipes = _recipes.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading = _isLoading.asStateFlow()

    init {
        loadFavorites()
    }

    fun loadFavorites() {
        viewModelScope.launch {
            _isLoading.value = true
            try {
                // Interceptor автоматично додасть токен
                val favorites = apiService.getFavoriteRecipes()
                _recipes.value = favorites
            } catch (e: Exception) {
                // Можна додати обробку помилок (наприклад, якщо юзер не залогінений)
                e.printStackTrace()
                _recipes.value = emptyList()
            } finally {
                _isLoading.value = false
            }
        }
    }
}
