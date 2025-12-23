package com.example.recipeapp.viewmodel // Змініть на ваш пакет

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.recipeapp.data.api.RecipeApiService // Ваш інтерфейс API
import com.example.recipeapp.data.model.DietTag // Ваші моделі
import com.example.recipeapp.data.model.User
import com.example.recipeapp.data.model.UserUpdateRequest
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class ProfileViewModel(private val api: RecipeApiService) : ViewModel() {

    private val _user = MutableStateFlow<User?>(null)
    val user = _user.asStateFlow()

    private val _allDiets = MutableStateFlow<List<DietTag>>(emptyList())
    val allDiets = _allDiets.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading = _isLoading.asStateFlow()

    // --- 👇 ДОДАНО: Стан для помилок ---
    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage = _errorMessage.asStateFlow()

    init {
        loadUserProfile()
    }

    private fun loadUserProfile() {
        viewModelScope.launch {
            _isLoading.value = true
            // Очищаємо помилку перед новим запитом
            _errorMessage.value = null
            try {
                _user.value = api.getProfile()
            } catch (e: Exception) {
                e.printStackTrace()
                // --- 👇 ДОДАНО: Запис помилки ---
                _errorMessage.value = "Помилка: ${e.localizedMessage}"
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun loadAllAvailableDiets() {
        if (_allDiets.value.isNotEmpty()) return

        viewModelScope.launch {
            try {
                val diets = api.getDiets()
                _allDiets.value = diets
            } catch (e: Exception) {
                e.printStackTrace()
                // Тут помилка не критична, можна не показувати юзеру
            }
        }
    }

    fun saveProfile(
        name: String,
        size: Int,
        skill: Int,
        selectedDietIds: List<Int>
    ) {
        viewModelScope.launch {
            _isLoading.value = true
            _errorMessage.value = null
            try {
                val request = UserUpdateRequest(
                    fullName = name,
                    familySize = size,
                    cookingSkillLevel = skill,
                    dietIds = selectedDietIds
                )
                _user.value = api.updateProfile(request)
            } catch (e: Exception) {
                e.printStackTrace()
                // --- 👇 ДОДАНО: Запис помилки ---
                _errorMessage.value = "Не вдалося зберегти: ${e.localizedMessage}"
            } finally {
                _isLoading.value = false
            }
        }
    }

    // --- 👇 ДОДАНО: Метод для очищення помилки ---
    fun clearError() {
        _errorMessage.value = null
    }
}