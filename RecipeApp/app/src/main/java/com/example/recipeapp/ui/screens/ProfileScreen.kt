package com.example.recipeapp.ui.screens
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Remove // Якщо немає Remove, використовуйте Minimize або намалюйте -
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.example.recipeapp.data.api.RecipeApiService
import com.example.recipeapp.viewmodel.ProfileViewModel // Імпорт вашої ViewModel
import com.example.recipeapp.viewmodel.ProfileViewModelFactory // Якщо використовуєте фабрику
import androidx.compose.material.icons.automirrored.filled.ExitToApp
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.outlined.RestaurantMenu
import androidx.compose.material.icons.outlined.People
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.foundation.basicMarquee
import androidx.compose.ui.text.style.TextOverflow


import com.example.recipeapp.data.model.DietTag
import com.example.recipeapp.data.model.User


@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProfileScreen(
    navController: NavController,
    apiService: RecipeApiService,
    onLogout: () -> Unit // Колбек для виходу з системи
) {
    // Ініціалізація ViewModel через фабрику
    val viewModel: ProfileViewModel = viewModel(
        factory = ProfileViewModelFactory(apiService)
    )

    val user by viewModel.user.collectAsState()
    val allDiets by viewModel.allDiets.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()
    val errorMessage by viewModel.errorMessage.collectAsState()

    // Стан режиму редагування
    var isEditing by remember { mutableStateOf(false) }
    var showLogoutDialog by remember { mutableStateOf(false) }

    // Стан для відображення помилок (Snackbar)
    val snackbarHostState = remember { SnackbarHostState() }
    if (showLogoutDialog) {
        AlertDialog(
            onDismissRequest = { showLogoutDialog = false },
            title = { Text("Вихід") },
            text = { Text("Ви впевнені, що хочете вийти з акаунту?") },
            confirmButton = {
                TextButton(
                    onClick = {
                        showLogoutDialog = false
                        onLogout() // Виконуємо реальний вихід
                    }
                ) { Text("Вийти", color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = {
                TextButton(onClick = { showLogoutDialog = false }) { Text("Скасувати") }
            }
        )
    }
    // Завантажуємо повний список дієт один раз при вході
    LaunchedEffect(Unit) {
        viewModel.loadAllAvailableDiets()
    }

    // Показ помилок через Snackbar
    LaunchedEffect(errorMessage) {
        errorMessage?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.clearError()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            CenterAlignedTopAppBar(
                title = { Text(if (isEditing) "Редагування профілю" else "Мій Профіль") },
                actions = {
                    if (isEditing) {
                        // Кнопка "Скасувати" (Хрестик)
                        IconButton(onClick = { isEditing = false }) {
                            Icon(Icons.Default.Close, contentDescription = "Cancel")
                        }
                    } else if (user != null) {
                        // Кнопка "Редагувати" (Олівець)
                        IconButton(onClick = { isEditing = true }) {
                            Icon(Icons.Default.Edit, contentDescription = "Edit")
                        }
                    }
                }
            )
        }
    ) { paddingValues ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
        ) {
            // 1. Стан завантаження (коли даних ще немає)
            if (user == null && isLoading) {
                CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
            }
            // 2. Основний контент
            else if (user != null) {
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .verticalScroll(rememberScrollState())
                        .padding(16.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {

                    // Аватар (Спільний для обох режимів)
                    Icon(
                        imageVector = Icons.Default.AccountCircle,
                        contentDescription = null,
                        modifier = Modifier.size(100.dp),
                        tint = MaterialTheme.colorScheme.primary
                    )
                    Spacer(modifier = Modifier.height(24.dp))

                    // Перемикання вмісту залежно від режиму
                    if (isEditing) {
                        // --- РЕЖИМ РЕДАГУВАННЯ ---
                        UserProfileEditor(
                            user = user!!,
                            allDiets = allDiets,
                            isLoading = isLoading,
                            onSave = { name, size, skill, diets ->
                                // 1. Зберігаємо дані на сервері
                                viewModel.saveProfile(name, size, skill, diets)

                                // 2. 🔥 ПОВІДОМЛЯЄМО FeedScreen, ЩО ТРЕБА ОНОВИТИСЬ
                                navController.previousBackStackEntry
                                    ?.savedStateHandle
                                    ?.set("profile_updated", true)

                                // 3. Виходимо з режиму редагування
                                isEditing = false
                            }
                        )
                    } else {
                        // --- РЕЖИМ ПЕРЕГЛЯДУ ---
                        UserProfileViewer(
                            user = user!!,
                            onLogoutClick = { showLogoutDialog = true }
                        )
                    }
                }
            }
        }
    }
}

// =====================================================================
// КОМПОНЕНТ: РЕЖИМ ПЕРЕГЛЯДУ (View Mode)
// =====================================================================
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun UserProfileViewer(
    user: User,
    onLogoutClick: () -> Unit
) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.fillMaxWidth()
    ) {
        // 1. Секція Заголовка (Ім'я та Email)
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.padding(horizontal = 24.dp)
        ) {
            // Визначаємо довжину імені
            val name = user.fullName ?: "Користувач"
            val isLongName = name.length > 20 // Поріг, після якого зменшуємо шрифт

            Text(
                text = name,
                // Якщо ім'я довге -> беремо headlineSmall (менший), інакше -> headlineMedium (великий)
                style = if (isLongName) MaterialTheme.typography.headlineSmall else MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center,
                lineHeight = if (isLongName) 28.sp else 32.sp, // Коригуємо висоту рядка
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
                color = MaterialTheme.colorScheme.onSurface,
                // Можна додати мінімальне розширення, якщо дозволяє контейнер
                modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp)
            )

            Spacer(modifier = Modifier.height(4.dp))

            Surface(
                color = MaterialTheme.colorScheme.surfaceVariant,
                shape = RoundedCornerShape(8.dp)
            ) {
                Text(
                    text = user.email,
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                )
            }
        }

        Spacer(modifier = Modifier.height(32.dp))

        // 2. Секція Статистики (Картки)
        // Використовуємо Row з weight, щоб картки були однакової ширини
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            InfoCard(
                icon = Icons.Outlined.People,
                label = "Сім'я",
                value = "${user.familySize} осіб",
                modifier = Modifier.weight(1f)
            )

            InfoCard(
                icon = Icons.Outlined.RestaurantMenu,
                label = "Навичка",
                value = getSkillLabel(user.cookingSkillLevel),
                modifier = Modifier.weight(1f)
            )
        }

        Spacer(modifier = Modifier.height(32.dp))

        // 3. Секція Дієт
        Column(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = "Вподобання та дієти",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurface
            )
            Spacer(modifier = Modifier.height(12.dp))

            if (user.diets.isEmpty()) {
                Text(
                    text = "Дієтичні обмеження відсутні",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.outline,
                    fontStyle = androidx.compose.ui.text.font.FontStyle.Italic
                )
            } else {
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    user.diets.forEach { diet ->
                        // Використовуємо кастомний чіп для кращого вигляду
                        Surface(
                            color = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.5f),
                            shape = RoundedCornerShape(8.dp),
                            border = null // Без обводки виглядає чистіше
                        ) {
                            Text(
                                text = diet.name,
                                style = MaterialTheme.typography.labelLarge,
                                color = MaterialTheme.colorScheme.onSecondaryContainer,
                                modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp)
                            )
                        }
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(48.dp))
        LogoutButton(onClick = onLogoutClick)
//        // 4. Кнопка Виходу (Стилізована)
//        OutlinedButton(
//            onClick = onLogout,
//            modifier = Modifier.fillMaxWidth(),
//            colors = ButtonDefaults.outlinedButtonColors(
//                contentColor = MaterialTheme.colorScheme.error
//            ),
//            border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.error.copy(alpha = 0.5f))
//        ) {
//            Icon(
//                imageVector = Icons.Outlined.Face, // Або Icons.Default.ExitToApp
//                contentDescription = null,
//                modifier = Modifier.size(18.dp)
//            )
//            Spacer(modifier = Modifier.width(8.dp))
//            Text("Вийти з акаунту")
//        }
    }
}

// --- Компонент красивої картки для статистики ---
@Composable
fun InfoCard(
    icon: ImageVector,
    label: String,
    value: String,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainerLow // Дуже світлий фон
        ),
        shape = RoundedCornerShape(16.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp) // Flat design
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(28.dp)
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = value,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurface
            )
            Text(
                text = label,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

// =====================================================================
// КОМПОНЕНТ: РЕЖИМ РЕДАГУВАННЯ (Edit Mode)
// =====================================================================
@OptIn(ExperimentalLayoutApi::class, ExperimentalMaterial3Api::class)
@Composable
fun UserProfileEditor(
    user: User,
    allDiets: List<DietTag>,
    isLoading: Boolean,
    onSave: (String, Int, Int, List<Int>) -> Unit
) {
    // Локальний стейт (чорновик)
    var name by remember { mutableStateOf(user.fullName ?: "") }
    var size by remember { mutableIntStateOf(user.familySize) }
    var skill by remember { mutableIntStateOf(user.cookingSkillLevel) }
    // Зберігаємо набір ID для зручної перевірки contains()
    var dietIds by remember { mutableStateOf(user.diets.map { it.id }.toSet()) }

    Column(horizontalAlignment = Alignment.CenterHorizontally) {

        // Поле імені
        OutlinedTextField(
            value = name,
            onValueChange = { name = it },
            label = { Text("Повне ім'я") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            shape = RoundedCornerShape(12.dp)
        )

        Spacer(modifier = Modifier.height(24.dp))

        // Лічильник порцій
        Text("Розмір порцій (за замовчуванням)")
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(top = 8.dp)
        ) {
            FilledIconButton(
                onClick = { if (size > 1) size-- },
                colors = IconButtonDefaults.filledIconButtonColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)
            ) {
                Icon(Icons.Default.Remove, contentDescription = "Minus")
            }

            Text(
                text = "$size",
                style = MaterialTheme.typography.headlineMedium,
                modifier = Modifier.padding(horizontal = 24.dp)
            )

            FilledIconButton(
                onClick = { if (size < 20) size++ },
                colors = IconButtonDefaults.filledIconButtonColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)
            ) {
                Icon(Icons.Default.Add, contentDescription = "Plus")
            }
        }

        Spacer(modifier = Modifier.height(24.dp))

        // Вибір навички
        Text("Рівень кулінара")
        Spacer(modifier = Modifier.height(8.dp))
        Row(modifier = Modifier.fillMaxWidth()) {
            listOf(1 to "Новачок", 2 to "Любитель", 3 to "Шеф").forEach { (lvl, lbl) ->
                val isSelected = skill == lvl
                OutlinedButton(
                    onClick = { skill = lvl },
                    modifier = Modifier
                        .weight(1f)
                        .padding(horizontal = 4.dp),
                    colors = ButtonDefaults.outlinedButtonColors(
                        containerColor = if (isSelected) MaterialTheme.colorScheme.primaryContainer else Color.Transparent,
                        contentColor = if (isSelected) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.primary
                    ),
                    border = BorderStroke(1.dp, if (isSelected) MaterialTheme.colorScheme.primary else Color.LightGray)
                ) {
                    Text(lbl, fontSize = 12.sp, maxLines = 1)
                }
            }
        }

        Spacer(modifier = Modifier.height(24.dp))

        // Вибір дієт (Multi-select)
        Text("Дієтичні вподобання")
        Spacer(modifier = Modifier.height(8.dp))

        if (allDiets.isEmpty()) {
            Text("Завантаження списку дієт...", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
        }

        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            allDiets.forEach { tag ->
                val isSelected = dietIds.contains(tag.id)
                FilterChip(
                    selected = isSelected,
                    onClick = {
                        dietIds = if (isSelected) dietIds - tag.id else dietIds + tag.id
                    },
                    label = { Text(tag.name) },
                    leadingIcon = if (isSelected) {
                        { Icon(Icons.Default.Check, null) }
                    } else null
                )
            }
        }

        Spacer(modifier = Modifier.height(32.dp))

        // Кнопка збереження
        Button(
            onClick = { onSave(name, size, skill, dietIds.toList()) },
            modifier = Modifier
                .fillMaxWidth()
                .height(50.dp),
            enabled = !isLoading
        ) {
            if (isLoading) {
                CircularProgressIndicator(modifier = Modifier.size(24.dp), color = Color.White)
            } else {
                Text("Зберегти зміни")
            }
        }
    }
}

// =====================================================================
// ДОПОМІЖНІ ЕЛЕМЕНТИ
// =====================================================================
@Composable
fun LogoutButton(onClick: () -> Unit) {
    OutlinedButton(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
        colors = ButtonDefaults.outlinedButtonColors(
            contentColor = MaterialTheme.colorScheme.error
        ),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.error.copy(alpha = 0.5f))
    ) {
        Icon(
            imageVector = Icons.AutoMirrored.Filled.ExitToApp,
            contentDescription = null,
            modifier = Modifier.size(18.dp)
        )
        Spacer(modifier = Modifier.width(8.dp))
        Text("Вийти з акаунту")
    }
}
@Composable
fun InfoItem(label: String, value: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(text = label, style = MaterialTheme.typography.bodySmall, color = Color.Gray)
        Text(text = value, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
    }
}

fun getSkillLabel(level: Int): String {
    return when (level) {
        1 -> "Новачок"
        2 -> "Любитель"
        3 -> "Шеф"
        else -> "Невідомо"
    }
}