package com.example.recipeapp.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import com.example.recipeapp.data.api.RecipeApiService
import com.example.recipeapp.data.manager.GoogleAuthManager
import com.example.recipeapp.data.manager.TokenManager

class AuthViewModelFactory(
    private val apiService: RecipeApiService,
    private val tokenManager: TokenManager,
    private val googleAuthManager: GoogleAuthManager
) : ViewModelProvider.Factory {

    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(AuthViewModel::class.java)) {
            @Suppress("UNCHECKED_CAST")
            return AuthViewModel(apiService, tokenManager, googleAuthManager) as T
        }
        throw IllegalArgumentException("Unknown ViewModel class")
    }
}