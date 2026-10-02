cmake_minimum_required(VERSION 3.22.1)

project("jarvisphonemizer")

find_library(log-lib log)

add_library(ttsespeak SHARED IMPORTED)
set_target_properties(ttsespeak PROPERTIES
        IMPORTED_LOCATION ${CMAKE_SOURCE_DIR}/../jniLibs/${ANDROID_ABI}/libttsespeak.so)

add_library(jarvisphonemizer SHARED espeak_wrapper.c)

target_include_directories(jarvisphonemizer PRIVATE ${CMAKE_SOURCE_DIR}/include)

target_link_libraries(jarvisphonemizer
        ttsespeak
        ${log-lib})
