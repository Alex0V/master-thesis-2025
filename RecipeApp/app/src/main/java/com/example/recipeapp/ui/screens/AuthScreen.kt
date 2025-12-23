package com.example.recipeapp.ui.screens

import android.widget.Toast
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.example.recipeapp.data.api.RecipeApiService
import com.example.recipeapp.data.manager.GoogleAuthManager
import com.example.recipeapp.data.manager.TokenManager
import com.example.recipeapp.ui.navigation.Screen
import com.example.recipeapp.viewmodel.AuthViewModel
import com.example.recipeapp.viewmodel.AuthViewModelFactory

@Composable
fun AuthScreen(
    navController: NavController,
    tokenManager: TokenManager,
    apiService: RecipeApiService
) {
    val context = LocalContext.current

    // Ініціалізуємо Google Manager тут, щоб передати у Factory
    val googleAuthManager = remember { GoogleAuthManager(context) }

    // 👇 СТВОРЮЄМО VIEWMODEL ЧЕРЕЗ ФАБРИКУ
    val viewModel: AuthViewModel = viewModel(
        factory = AuthViewModelFactory(apiService, tokenManager, googleAuthManager)
    )

    // Підписуємось на стан (Loading)
    val isLoading by viewModel.isLoading.collectAsState()

    // Локальний стан полів вводу
    var isRegister by remember { mutableStateOf(false) }
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var fullName by remember { mutableStateOf("") }
    var passwordVisible by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text(
            text = if (isRegister) "Створити акаунт" else "З поверненням! 👋",
            style = MaterialTheme.typography.headlineMedium,
            color = MaterialTheme.colorScheme.primary
        )

        Spacer(modifier = Modifier.height(32.dp))

        if (isRegister) {
            OutlinedTextField(
                value = fullName,
                onValueChange = { fullName = it },
                label = { Text("Повне ім'я") },
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(modifier = Modifier.height(16.dp))
        }

        OutlinedTextField(
            value = email,
            onValueChange = { email = it },
            label = { Text("Email") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
            modifier = Modifier.fillMaxWidth()
        )

        Spacer(modifier = Modifier.height(16.dp))

        OutlinedTextField(
            value = password,
            onValueChange = { password = it },
            label = { Text("Пароль") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            visualTransformation = if (passwordVisible) VisualTransformation.None else PasswordVisualTransformation(),
            trailingIcon = {
                IconButton(onClick = { passwordVisible = !passwordVisible }) {
                    Icon(
                        imageVector = if (passwordVisible) Icons.Filled.Visibility else Icons.Filled.VisibilityOff,
                        contentDescription = "Toggle password"
                    )
                }
            },
            modifier = Modifier.fillMaxWidth()
        )

        Spacer(modifier = Modifier.height(24.dp))

        // --- КНОПКА ДІЇ ---
        Button(
            onClick = {
                // Колбеки для навігації
                val onSuccess = {
                    Toast.makeText(context, "Успішно!", Toast.LENGTH_SHORT).show()
                    navController.navigate(Screen.Home.route) {
                        popUpTo(Screen.Auth.route) { inclusive = true }
                    }
                }
                val onError = { msg: String ->
                    Toast.makeText(context, msg, Toast.LENGTH_LONG).show()
                }

                if (isRegister) {
                    viewModel.register(email, password, fullName, onSuccess, onError)
                } else {
                    viewModel.login(email, password, onSuccess, onError)
                }
            },
            modifier = Modifier.fillMaxWidth().height(50.dp),
            enabled = !isLoading
        ) {
            if (isLoading) {
                CircularProgressIndicator(color = MaterialTheme.colorScheme.onPrimary, modifier = Modifier.size(24.dp))
            } else {
                Text(if (isRegister) "Зареєструватися" else "Увійти", fontSize = 18.sp)
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // --- КНОПКА GOOGLE ---
        OutlinedButton(
            onClick = {
                viewModel.googleLogin(
                    onSuccess = {
                        Toast.makeText(context, "Вхід через Google успішний!", Toast.LENGTH_SHORT).show()
                        navController.navigate(Screen.Home.route) {
                            popUpTo(Screen.Auth.route) { inclusive = true }
                        }
                    },
                    onError = { msg ->
                        if (msg != "Вхід скасовано") {
                            Toast.makeText(context, msg, Toast.LENGTH_LONG).show()
                        }
                    }
                )
            },
            modifier = Modifier.fillMaxWidth().height(50.dp),
            enabled = !isLoading
        ) {
            Icon(
                imageVector = Icons.Default.AccountCircle,
                contentDescription = null,
                modifier = Modifier.size(24.dp)
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text("Увійти через Google")
        }

        Spacer(modifier = Modifier.height(24.dp))

        TextButton(onClick = { isRegister = !isRegister }) {
            Text(if (isRegister) "Вже маєте акаунт? Увійти" else "Немає акаунту? Зареєструватися")
        }
    }
}