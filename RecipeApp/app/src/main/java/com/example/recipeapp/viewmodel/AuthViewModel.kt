package com.example.recipeapp.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.recipeapp.data.api.RecipeApiService
import com.example.recipeapp.data.manager.GoogleAuthManager
import com.example.recipeapp.data.manager.TokenManager
import com.example.recipeapp.data.model.GoogleAuthRequest
import com.example.recipeapp.data.model.LoginRequest
import com.example.recipeapp.data.model.RegisterRequest
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class AuthViewModel(
    private val apiService: RecipeApiService,
    private val tokenManager: TokenManager,
    private val googleAuthManager: GoogleAuthManager
) : ViewModel() {

    // Стан завантаження (True - показуємо спіннер)
    private val _isLoading = MutableStateFlow(false)
    val isLoading = _isLoading.asStateFlow()

    // Логіка звичайного входу
    fun login(email: String, pass: String, onSuccess: () -> Unit, onError: (String) -> Unit) {
        if (email.isBlank() || pass.isBlank()) {
            onError("Заповніть всі поля")
            return
        }

        _isLoading.value = true
        viewModelScope.launch {
            try {
                val response = apiService.login(LoginRequest(email, pass))
                tokenManager.saveTokens(response.accessToken, response.refreshToken)
                onSuccess()
            } catch (e: Exception) {
                onError(e.message ?: "Помилка входу")
            } finally {
                _isLoading.value = false
            }
        }
    }

    // Логіка реєстрації
    fun register(email: String, pass: String, name: String, onSuccess: () -> Unit, onError: (String) -> Unit) {
        if (email.isBlank() || pass.isBlank() || name.isBlank()) {
            onError("Заповніть всі поля")
            return
        }

        _isLoading.value = true
        viewModelScope.launch {
            try {
                val response = apiService.register(RegisterRequest(email, pass, name))
                tokenManager.saveTokens(response.accessToken, response.refreshToken)
                onSuccess()
            } catch (e: Exception) {
                onError(e.message ?: "Помилка реєстрації")
            } finally {
                _isLoading.value = false
            }
        }
    }

    // Логіка Google входу
    fun googleLogin(onSuccess: () -> Unit, onError: (String) -> Unit) {
        viewModelScope.launch {
            _isLoading.value = true
            // 1. Відкриваємо вікно вибору акаунту
            val token = googleAuthManager.signIn()

            if (token != null) {
                try {
                    // 2. Шлемо токен на бекенд
                    val response = apiService.googleLogin(GoogleAuthRequest(token))
                    tokenManager.saveTokens(response.accessToken, response.refreshToken)
                    onSuccess()
                } catch (e: Exception) {
                    onError("Помилка сервера: ${e.message}")
                }
            } else {
                onError("Вхід скасовано")
            }
            _isLoading.value = false
        }
    }
}