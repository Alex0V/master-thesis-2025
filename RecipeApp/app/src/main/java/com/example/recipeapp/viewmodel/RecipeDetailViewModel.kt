package com.example.recipeapp.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.recipeapp.data.api.RecipeApiService
import com.example.recipeapp.data.manager.TokenManager
import com.example.recipeapp.data.model.RecipeDetails
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class RecipeDetailViewModel(
    private val apiService: RecipeApiService
) : ViewModel() {

    // Стан даних рецепта (спочатку null)
    private val _recipe = MutableStateFlow<RecipeDetails?>(null)
    val recipe = _recipe.asStateFlow()

    // Cтан для кнопки лайка
    private val _isFavorite = MutableStateFlow(false)
    val isFavorite = _isFavorite.asStateFlow()

    // Стан завантаження (спочатку true, бо ми відразу вантажимо)
    private val _isLoading = MutableStateFlow(true)
    val isLoading = _isLoading.asStateFlow()

    // Стан помилки (опціонально, щоб показати Toast)
    private val _error = MutableStateFlow<String?>(null)
    val error = _error.asStateFlow()

    fun loadRecipe(id: Int) {
        viewModelScope.launch {
            _isLoading.value = true
            _error.value = null
            try {
                // Викликаємо наш новий метод API
                val details = apiService.getRecipeDetails(id)
                _recipe.value = details

                // Ініціалізуємо стан кнопки даними з сервера
                _isFavorite.value = details.isFavorite
            } catch (e: Exception) {
                e.printStackTrace()
                _error.value = "Помилка завантаження: ${e.localizedMessage}"
            } finally {
                _isLoading.value = false
            }
        }
    }
    // Логіка перемикання лайка
    fun toggleFavorite() {
        val currentRecipe = _recipe.value ?: return
        val wasFavorite = _isFavorite.value

        viewModelScope.launch {
            // 1. Оптимістично змінюємо UI (миттєвий відгук)
            _isFavorite.value = !wasFavorite

            try {
                if (wasFavorite) {
                    // Було улюбленим -> Видаляємо
                    apiService.removeFromFavorites(currentRecipe.id)
                } else {
                    // Не було -> Додаємо
                    apiService.addToFavorites(currentRecipe.id)
                }
            } catch (e: Exception) {
                // 2. Якщо помилка — повертаємо стан назад і показуємо Toast/Error
                _isFavorite.value = wasFavorite
                e.printStackTrace()
            }
        }
    }
}
