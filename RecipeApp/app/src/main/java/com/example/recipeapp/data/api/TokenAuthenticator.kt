package com.example.recipeapp.data.api

import com.example.recipeapp.data.manager.TokenManager
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import okhttp3.Authenticator
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route

class TokenAuthenticator(
    private val tokenManager: TokenManager,
    private val apiService: RecipeApiService
) : Authenticator {

    override fun authenticate(route: Route?, response: Response): Request? {
        // 👇 ВИПРАВЛЕННЯ: Рахуємо кількість спроб вручну
        if (responseCount(response) >= 3) {
            return null // Здаємося після 3-х спроб
        }

        // 1. Дістаємо поточний Refresh Token
        val refreshToken = runBlocking {
            tokenManager.refreshToken.first()
        }

        if (refreshToken.isNullOrBlank()) {
            return null
        }

        return try {
            // 2. Робимо запит на оновлення
            val refreshResponse = apiService.refreshToken(mapOf("refresh_token" to refreshToken)).execute()

            if (refreshResponse.isSuccessful) {
                val newTokens = refreshResponse.body()

                if (newTokens != null) {
                    // 3. Зберігаємо нові токени
                    runBlocking {
                        tokenManager.saveTokens(newTokens.accessToken, newTokens.refreshToken)
                    }

                    // 4. Повертаємо новий запит з НОВИМ токеном
                    response.request.newBuilder()
                        .header("Authorization", "Bearer ${newTokens.accessToken}")
                        .build()
                } else {
                    null
                }
            } else {
                // Refresh Token прострочений — вилогінюємо
                runBlocking { tokenManager.clearTokens() }
                null
            }
        } catch (e: Exception) {
            null
        }
    }

    // 👇 ДОДАЛИ ЦЮ ФУНКЦІЮ
    // Вона рахує, скільки разів сервер відповів нам помилкою підряд
    private fun responseCount(response: Response): Int {
        var result = 1
        var prior = response.priorResponse
        while (prior != null) {
            result++
            prior = prior.priorResponse
        }
        return result
    }
}