if(NOT TARGET ethermobile-core)
    find_package(Qt6 REQUIRED COMPONENTS Core DBus Network)
    add_library(ethermobile-core STATIC
        ${CMAKE_CURRENT_LIST_DIR}/mobile.cpp ${CMAKE_CURRENT_LIST_DIR}/mobile_config.cpp
        ${CMAKE_CURRENT_LIST_DIR}/mobile_modem.cpp ${CMAKE_CURRENT_LIST_DIR}/mobile_usage.cpp ${CMAKE_CURRENT_LIST_DIR}/mobile_data.cpp
        ${CMAKE_CURRENT_LIST_DIR}/mobile.h ${CMAKE_CURRENT_LIST_DIR}/provider.h
        ${CMAKE_CURRENT_LIST_DIR}/sms.cpp ${CMAKE_CURRENT_LIST_DIR}/sms.h
        ${CMAKE_CURRENT_LIST_DIR}/dbustypes.h ${CMAKE_CURRENT_LIST_DIR}/policy.h)
    target_include_directories(ethermobile-core PUBLIC ${CMAKE_CURRENT_LIST_DIR})
    target_link_libraries(ethermobile-core PUBLIC Qt6::Core Qt6::DBus Qt6::Network)
    target_compile_options(ethermobile-core PRIVATE -Wall -Wextra -Wpedantic)
endif()
